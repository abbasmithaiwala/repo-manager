#!/usr/bin/env python3
"""
GitHub Commit Deleter (Human-in-Loop)
Safely deletes commits by showing preview and asking for confirmation before force push.
"""

import os
import json
import subprocess
import tempfile
import argparse
from datetime import datetime
from typing import Dict, List, Tuple

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.prompt import Confirm
    from rich import box
    import questionary
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("⚠️  For better experience, install: pip install -r requirements.txt")
    print()


class GitHubCommitDeleter:
    """Handles deleting GitHub commits using local git operations with human confirmation."""

    def __init__(self, token: str, use_rich: bool = True):
        """
        Initialize the deleter with GitHub authentication.

        Args:
            token: GitHub personal access token
            use_rich: Use rich formatting (if available)
        """
        self.token = token
        self.results = []
        self.skipped_for_later = []
        self.stats = {
            "total_repos": 0,
            "processed_repos": 0,
            "skipped_repos": 0,
            "total_commits": 0,
            "deleted_commits": 0,
            "skipped_commits": 0
        }
        self.use_rich = use_rich and RICH_AVAILABLE
        if self.use_rich:
            self.console = Console()

    def print(self, *args, **kwargs):
        """Print with rich if available, otherwise regular print."""
        if self.use_rich:
            self.console.print(*args, **kwargs)
        else:
            print(*args, **kwargs)

    def load_commits_file(self, filepath: str = "commits.json") -> List[Dict]:
        """Load commits from JSON file."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Commits file not found: {filepath}")

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            # Handle different file formats
            commits = []

            # Format 1: Standard commits.json format
            if 'commits' in data:
                commits = data['commits']

            # Format 2: Skipped commits format
            elif 'skipped_commits' in data:
                skipped = data['skipped_commits']
                # Convert skipped format to standard format
                for item in skipped:
                    commits.append({
                        "repository": item.get("repository", "").replace("/git", ""),  # Remove /git suffix
                        "commit_id": item.get("commit_sha"),
                        "commit_message": item.get("commit_message", ""),
                        "timestamp": item.get("timestamp", "1970-01-01T00:00:00Z"),  # Default timestamp
                        "url": f"https://github.com/{item.get('repository', '').replace('/git', '')}/commit/{item.get('commit_sha', '')}"
                    })

            if not commits:
                raise ValueError(f"No commits found in {filepath}")

            if self.use_rich:
                self.console.print(f"[green]✓[/green] Loaded {len(commits)} commits from {filepath}")
            else:
                print(f"✓ Loaded {len(commits)} commits from {filepath}")
            return commits

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {filepath}: {e}")

    def run_command(self, command: List[str], cwd: str = None) -> Tuple[bool, str, str]:
        """Run a shell command and return output."""
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300
            )
            return (result.returncode == 0, result.stdout, result.stderr)
        except subprocess.TimeoutExpired:
            return (False, "", "Command timed out after 5 minutes")
        except Exception as e:
            return (False, "", str(e))

    def check_git_installed(self) -> bool:
        """Check if git is installed."""
        success, _, _ = self.run_command(["git", "--version"])
        return success

    def clone_repository(self, repository: str, clone_dir: str) -> Tuple[bool, str]:
        """Clone a repository using HTTPS with token authentication."""
        repo_url = f"https://{self.token}@github.com/{repository}.git"

        success, stdout, stderr = self.run_command(
            ["git", "clone", "--quiet", repo_url, clone_dir]
        )

        if not success:
            error_msg = stderr.replace(self.token, "***TOKEN***")
            return (False, f"Clone failed: {error_msg}")

        return (True, None)

    def configure_git_user(self, repo_dir: str) -> Tuple[bool, str]:
        """Configure git user for the repository."""
        commands = [
            ["git", "config", "user.name", "GitHub Script"],
            ["git", "config", "user.email", "noreply@github.com"]
        ]

        for cmd in commands:
            success, _, stderr = self.run_command(cmd, cwd=repo_dir)
            if not success:
                return (False, f"Git config failed: {stderr}")

        return (True, None)

    def get_commit_details(self, repo_dir: str, commit_sha: str) -> Dict:
        """Get detailed information about a commit including files changed."""
        details = {
            "sha": commit_sha,
            "message": "",
            "author": "",
            "date": "",
            "files": []
        }

        # Get commit message, author, and date
        success, output, _ = self.run_command(
            ["git", "show", "--quiet", "--format=%s%n%an%n%ai", commit_sha],
            cwd=repo_dir
        )

        if success:
            lines = output.strip().split('\n')
            if len(lines) >= 3:
                details["message"] = lines[0]
                details["author"] = lines[1]
                details["date"] = lines[2]

        # Get list of files changed
        success, output, _ = self.run_command(
            ["git", "show", "--name-only", "--format=", commit_sha],
            cwd=repo_dir
        )

        if success:
            files = [f.strip() for f in output.strip().split('\n') if f.strip()]
            details["files"] = files

        return details

    def check_commits_safety(self, repo_dir: str, commits: List[Dict]) -> Tuple[bool, str, List[str]]:
        """
        Check if it's safe to delete commits (no commits after them).

        Args:
            repo_dir: Repository directory
            commits: List of commits to check

        Returns:
            Tuple of (is_safe: bool, error_message: str, commits_after: List[str])
        """
        # Get current HEAD
        success, head_sha, _ = self.run_command(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_dir
        )

        if not success:
            return (False, "Failed to get HEAD commit", [])

        head_sha = head_sha.strip()

        # Find the most recent commit we want to delete
        commit_shas = [c.get("commit_id") for c in commits]

        # For each commit to delete, check if it's the HEAD or if there are commits after it
        commits_after = []

        for commit_sha in commit_shas:
            # Get commits between this commit and HEAD
            success, output, _ = self.run_command(
                ["git", "rev-list", f"{commit_sha}..HEAD"],
                cwd=repo_dir
            )

            if success and output.strip():
                # There are commits after this one
                after_list = output.strip().split('\n')
                # Filter out commits that are in our deletion list
                after_list = [sha for sha in after_list if sha not in commit_shas]

                if after_list:
                    commits_after.extend(after_list)

        # Remove duplicates
        commits_after = list(set(commits_after))

        if commits_after:
            # Get details of commits that would be affected
            affected_commits = []
            for sha in commits_after[:5]:  # Show first 5
                success, msg, _ = self.run_command(
                    ["git", "log", "--format=%s", "-n", "1", sha],
                    cwd=repo_dir
                )
                if success:
                    affected_commits.append(f"{sha[:8]}... - {msg.strip()}")

            error_msg = (
                f"UNSAFE: Found {len(commits_after)} commit(s) AFTER the commits you want to delete.\n"
                f"Deleting would erase these newer commits:\n" +
                "\n".join(f"  - {c}" for c in affected_commits[:5])
            )

            if len(commits_after) > 5:
                error_msg += f"\n  ... and {len(commits_after) - 5} more commits"

            return (False, error_msg, commits_after)

        # Check if any of the commits to delete are the HEAD
        if head_sha in commit_shas:
            return (True, "Safe: Commits to delete are at HEAD (no commits after them)", [])

        # Additional check: are all commits to delete on the current branch?
        for commit_sha in commit_shas:
            success, _, _ = self.run_command(
                ["git", "merge-base", "--is-ancestor", commit_sha, "HEAD"],
                cwd=repo_dir
            )
            if not success:
                return (False, f"Commit {commit_sha[:8]}... is not an ancestor of HEAD", [])

        return (True, "Safe: All commits can be deleted without affecting other commits", [])

    def preview_repository_commits(self, repository: str, commits: List[Dict]) -> bool:
        """
        Show preview of commits to be deleted and ask for confirmation.

        Returns:
            True if user confirms deletion, False otherwise
        """
        repo_url = f"https://github.com/{repository}"

        if self.use_rich:
            self.console.print()
            self.console.print(Panel.fit(
                f"[bold cyan]{repository}[/bold cyan]\n[dim]{repo_url}[/dim]",
                title=f"[bold]Repository[/bold]",
                border_style="cyan"
            ))
            self.console.print(f"[yellow]Found {len(commits)} commit(s) to delete[/yellow]\n")
        else:
            print(f"\n{'='*70}")
            print(f"REPOSITORY: {repository}")
            print(f"URL: {repo_url}")
            print(f"{'='*70}")
            print(f"Found {len(commits)} commit(s) to delete\n")

        # Clone repository to get commit details
        with tempfile.TemporaryDirectory() as temp_dir:
            clone_dir = os.path.join(temp_dir, "repo")

            if self.use_rich:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=self.console,
                ) as progress:
                    task = progress.add_task("Cloning repository...", total=None)
                    success, error = self.clone_repository(repository, clone_dir)
                    progress.update(task, completed=True)
            else:
                print("Cloning repository to preview commits...")
                success, error = self.clone_repository(repository, clone_dir)

            if not success:
                if self.use_rich:
                    self.console.print(f"[red]✗ Failed to clone repository: {error}[/red]")
                    self.console.print("[yellow]Cannot preview commits. Skipping repository.[/yellow]\n")
                else:
                    print(f"✗ Failed to clone repository: {error}")
                    print("Cannot preview commits. Skipping repository.\n")
                return False

            # CRITICAL: Check if it's safe to delete these commits
            if self.use_rich:
                self.console.print("\n[cyan]🔍 Performing safety check...[/cyan]")
            else:
                print("\n🔍 Performing safety check...")

            is_safe, safety_message, commits_after = self.check_commits_safety(clone_dir, commits)

            if not is_safe:
                if self.use_rich:
                    self.console.print(Panel(
                        f"[red]{safety_message}[/red]",
                        title="[bold red]🛑 SAFETY CHECK FAILED[/bold red]",
                        border_style="red"
                    ))
                    self.console.print("[red]❌ Cannot proceed with deletion - would affect other commits![/red]")
                    self.console.print("[yellow]This repository will be automatically skipped.[/yellow]\n")
                else:
                    print(f"\n{'='*70}")
                    print(f"🛑 SAFETY CHECK FAILED")
                    print(f"{'='*70}")
                    print(f"{safety_message}")
                    print(f"\n{'='*70}")
                    print(f"❌ Cannot proceed with deletion - would affect other commits!")
                    print(f"This repository will be automatically skipped.\n")
                return False

            if self.use_rich:
                self.console.print(f"[green]✅ Safety check passed:[/green] {safety_message}\n")
            else:
                print(f"✅ Safety check passed: {safety_message}\n")

            # Show details for each commit
            if self.use_rich:
                # Create a table for commits
                table = Table(title="Commits to Delete", box=box.ROUNDED, show_lines=True)
                table.add_column("#", style="cyan", width=4)
                table.add_column("SHA", style="yellow", width=20)
                table.add_column("Message", style="white", width=40)
                table.add_column("Author", style="green", width=20)
                table.add_column("Files Changed", style="magenta", width=12)

                for idx, commit in enumerate(commits, 1):
                    commit_sha = commit.get("commit_id")
                    details = self.get_commit_details(clone_dir, commit_sha)

                    short_sha = f"{commit_sha[:8]}...{commit_sha[-8:]}"
                    message = details['message'][:37] + "..." if len(details['message']) > 40 else details['message']
                    author = details['author'][:17] + "..." if len(details['author']) > 20 else details['author']
                    file_count = str(len(details['files']))

                    table.add_row(str(idx), short_sha, message, author, file_count)

                self.console.print(table)

                # Show file details for each commit
                for idx, commit in enumerate(commits, 1):
                    commit_sha = commit.get("commit_id")
                    details = self.get_commit_details(clone_dir, commit_sha)

                    if details['files']:
                        files_display = "\n".join([f"  • {f}" for f in details['files'][:10]])
                        if len(details['files']) > 10:
                            files_display += f"\n  ... and {len(details['files']) - 10} more files"

                        self.console.print(Panel(
                            files_display,
                            title=f"[bold]Commit {idx}/{len(commits)} - Files Changed[/bold]",
                            border_style="dim",
                            expand=False
                        ))

            else:
                for idx, commit in enumerate(commits, 1):
                    commit_sha = commit.get("commit_id")
                    details = self.get_commit_details(clone_dir, commit_sha)

                    print(f"\n--- Commit {idx}/{len(commits)} ---")
                    print(f"SHA:     {commit_sha[:8]}...{commit_sha[-8:]}")
                    print(f"Message: {details['message']}")
                    print(f"Author:  {details['author']}")
                    print(f"Date:    {details['date']}")
                    print(f"Files changed ({len(details['files'])}):")

                    for file in details['files'][:10]:
                        print(f"  - {file}")

                    if len(details['files']) > 10:
                        print(f"  ... and {len(details['files']) - 10} more files")

        # Ask for confirmation
        if self.use_rich:
            self.console.print()
            self.console.print(Panel(
                f"[bold red]⚠️  WARNING: This will PERMANENTLY DELETE these {len(commits)} commit(s)[/bold red]\n"
                f"[red]⚠️  This operation uses FORCE PUSH and rewrites git history![/red]\n"
                f"[green]✅ SAFE: No commits will be affected after the ones being deleted[/green]",
                border_style="yellow",
                box=box.DOUBLE
            ))
            self.console.print()

            # Use questionary for interactive buttons
            try:
                choice = questionary.select(
                    f"What would you like to do with {repository}?",
                    choices=[
                        questionary.Choice("✅ Yes - Delete these commits", value="yes"),
                        questionary.Choice("❌ No - Skip and mark for later", value="no"),
                        questionary.Choice("⏭️  Skip this repository", value="skip"),
                    ],
                    style=questionary.Style([
                        ('selected', 'bold'),
                        ('pointer', 'cyan bold'),
                    ])
                ).ask()

                if choice == "yes":
                    self.console.print("[green]✅ Confirmed - proceeding with deletion...[/green]\n")
                    return True
                elif choice == "no":
                    self.console.print("[yellow]❌ Marking commits for later review[/yellow]")
                    return False
                else:  # skip
                    self.console.print("[yellow]⏭️  Skipping this repository[/yellow]")
                    return False

            except (KeyboardInterrupt, EOFError):
                self.console.print("\n[yellow]Operation cancelled by user[/yellow]")
                return False

        else:
            # Fallback to text input
            print(f"\n{'='*70}")
            print(f"⚠️  WARNING: This will PERMANENTLY DELETE these {len(commits)} commit(s)")
            print(f"⚠️  This operation uses FORCE PUSH and rewrites git history!")
            print(f"✅ SAFE: No commits will be affected after the ones being deleted")
            print(f"{'='*70}\n")

            while True:
                response = input(f"Delete these commits from {repository}? (yes/no/skip): ").strip().lower()

                if response in ['yes', 'y']:
                    return True
                elif response in ['no', 'n']:
                    print("❌ Aborting - commits will be marked for later review")
                    return False
                elif response in ['skip', 's']:
                    print("⏭️  Skipping this repository")
                    return False
                else:
                    print("Please enter 'yes', 'no', or 'skip'")

    def delete_commits_from_repo(self, repository: str, commits: List[Dict]) -> Dict:
        """
        Delete multiple commits from a repository using force push.

        Args:
            repository: Full repository name (owner/repo)
            commits: List of commits to delete

        Returns:
            Dictionary with operation results
        """
        result = {
            "repository": repository,
            "total_commits": len(commits),
            "deleted_commits": 0,
            "failed_commits": 0,
            "status": "pending",
            "error_message": None,
            "commit_details": []
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            clone_dir = os.path.join(temp_dir, "repo")

            # Clone repository
            self.print(f"\n[cyan]🔄 Cloning {repository}...[/cyan]" if self.use_rich else f"\n🔄 Cloning {repository}...")
            success, error = self.clone_repository(repository, clone_dir)
            if not success:
                result["status"] = "failed"
                result["error_message"] = error
                return result

            # Configure git
            success, error = self.configure_git_user(clone_dir)
            if not success:
                result["status"] = "failed"
                result["error_message"] = error
                return result

            # Get current branch
            success, current_branch, _ = self.run_command(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=clone_dir
            )
            if not success:
                result["status"] = "failed"
                result["error_message"] = "Failed to get current branch"
                return result

            current_branch = current_branch.strip()

            # Get current HEAD
            success, head_sha, _ = self.run_command(
                ["git", "rev-parse", "HEAD"],
                cwd=clone_dir
            )
            if not success:
                result["status"] = "failed"
                result["error_message"] = "Failed to get HEAD"
                return result

            head_sha = head_sha.strip()

            # Collect all commit SHAs to delete
            commit_shas = [c.get("commit_id") for c in commits]

            # Verify all commits exist
            self.print(f"  [dim]🔍 Verifying {len(commits)} commit(s)...[/dim]" if self.use_rich else f"  🔍 Verifying {len(commits)} commit(s)...")
            all_commits_valid = True
            for commit_sha in commit_shas:
                success, _, _ = self.run_command(
                    ["git", "rev-parse", "--verify", commit_sha],
                    cwd=clone_dir
                )
                if not success:
                    commit_msg = next((c.get("commit_message", "")[:60] for c in commits if c.get("commit_id") == commit_sha), "")
                    self.print(f"     [yellow]⚠️  Commit {commit_sha[:8]}... not found[/yellow]" if self.use_rich else f"     ⚠️  Commit {commit_sha[:8]}... not found")
                    result["commit_details"].append({
                        "sha": commit_sha,
                        "status": "not_found",
                        "message": commit_msg
                    })
                    result["failed_commits"] += 1
                    all_commits_valid = False

            if not all_commits_valid:
                result["status"] = "failed"
                result["error_message"] = "Some commits were not found"
                return result

            self.print(f"     [green]✓ All commits verified[/green]" if self.use_rich else f"     ✓ All commits verified")

            # Find the oldest commit to delete
            sorted_commits = sorted(commits, key=lambda x: x.get('timestamp', ''))
            oldest_commit_sha = sorted_commits[0].get("commit_id")

            # Get the parent of the oldest commit (this is where we'll reset to)
            success, parent_sha, stderr = self.run_command(
                ["git", "rev-parse", f"{oldest_commit_sha}^"],
                cwd=clone_dir
            )

            if not success:
                result["status"] = "failed"
                result["error_message"] = f"Failed to get parent commit: {stderr}"
                return result

            parent_sha = parent_sha.strip()

            self.print(f"\n  [bold]🗑️  Deleting {len(commits)} commit(s) from history...[/bold]" if self.use_rich else f"\n  🗑️  Deleting {len(commits)} commit(s) from history...")
            self.print(f"     [dim]Resetting HEAD from {head_sha[:8]}... to {parent_sha[:8]}...[/dim]" if self.use_rich else f"     Resetting HEAD from {head_sha[:8]}... to {parent_sha[:8]}...")

            # Reset HEAD to the parent of the oldest commit (effectively deleting all commits)
            success, stdout, stderr = self.run_command(
                ["git", "reset", "--hard", parent_sha],
                cwd=clone_dir
            )

            if not success:
                result["status"] = "failed"
                result["error_message"] = f"Git reset failed: {stderr}"
                return result

            self.print(f"     [green]✓ Reset successful[/green]" if self.use_rich else f"     ✓ Reset successful")

            # Mark all commits as deleted
            for commit in commits:
                commit_sha = commit.get("commit_id")
                commit_msg = commit.get("commit_message", "")[:60]
                result["deleted_commits"] += 1
                result["commit_details"].append({
                    "sha": commit_sha,
                    "status": "deleted",
                    "message": commit_msg
                })
                self.print(f"     [green]✓[/green] Deleted: [yellow]{commit_sha[:8]}...[/yellow] - [dim]{commit_msg}[/dim]" if self.use_rich else f"     ✓ Deleted: {commit_sha[:8]}... - {commit_msg}")

            # Force push
            self.print(f"\n  [bold cyan]🚀 Force pushing to {current_branch}...[/bold cyan]" if self.use_rich else f"\n  🚀 Force pushing to {current_branch}...")

            success, stdout, stderr = self.run_command(
                ["git", "push", "--force", "origin", current_branch],
                cwd=clone_dir
            )

            if success:
                result["status"] = "success"
                self.print(f"     [green]✓ Successfully force pushed to {current_branch}[/green]" if self.use_rich else f"     ✓ Successfully force pushed to {current_branch}")
                self.print(f"     [green bold]✓ Deleted {result['deleted_commits']} commit(s) from history[/green bold]" if self.use_rich else f"     ✓ Deleted {result['deleted_commits']} commit(s) from history")
            else:
                result["status"] = "partial"
                error_msg = stderr.replace(self.token, "***TOKEN***")
                result["error_message"] = f"Force push failed: {error_msg}"
                self.print(f"     [red]✗ Force push failed: {error_msg}[/red]" if self.use_rich else f"     ✗ Force push failed: {error_msg}")

        return result

    def process_all_commits(self, commits: List[Dict]) -> None:
        """Process all commits with human-in-loop confirmation."""
        # Group commits by repository
        commits_by_repo = {}
        for commit in commits:
            repo = commit.get("repository")
            if repo not in commits_by_repo:
                commits_by_repo[repo] = []
            commits_by_repo[repo].append(commit)

        self.stats["total_repos"] = len(commits_by_repo)
        self.stats["total_commits"] = len(commits)

        if self.use_rich:
            self.console.print()
            self.console.print(Panel(
                f"[bold]Total repositories:[/bold] {len(commits_by_repo)}\n"
                f"[bold]Total commits to delete:[/bold] {len(commits)}",
                title="[bold cyan]COMMIT DELETION PLAN[/bold cyan]",
                border_style="cyan",
                box=box.DOUBLE
            ))
        else:
            print(f"\n{'='*70}")
            print(f"COMMIT DELETION PLAN")
            print(f"{'='*70}")
            print(f"Total repositories: {len(commits_by_repo)}")
            print(f"Total commits to delete: {len(commits)}")
            print(f"{'='*70}\n")

        # Process each repository
        for idx, (repository, repo_commits) in enumerate(commits_by_repo.items(), 1):
            if self.use_rich:
                self.console.print(f"\n[bold cyan]━━━ Repository {idx}/{len(commits_by_repo)} ━━━[/bold cyan]")
            else:
                print(f"\n\n[Repository {idx}/{len(commits_by_repo)}]")

            # Show preview and get confirmation
            confirmed = self.preview_repository_commits(repository, repo_commits)

            if not confirmed:
                # Mark commits for later review
                self.stats["skipped_repos"] += 1
                self.stats["skipped_commits"] += len(repo_commits)

                for commit in repo_commits:
                    self.skipped_for_later.append({
                        "repository": repository,
                        "commit_sha": commit.get("commit_id"),
                        "commit_message": commit.get("commit_message"),
                        "reason": "User declined deletion"
                    })

                continue

            # User confirmed - proceed with deletion
            result = self.delete_commits_from_repo(repository, repo_commits)

            # Update statistics
            self.stats["processed_repos"] += 1
            self.stats["deleted_commits"] += result["deleted_commits"]

            # Store result
            self.results.append(result)

            # Show result summary
            if result["status"] == "success":
                if self.use_rich:
                    self.console.print(Panel(
                        f"[green]Successfully deleted {result['deleted_commits']} commit(s)[/green]",
                        title=f"[bold green]✅ {repository}[/bold green]",
                        border_style="green"
                    ))
                else:
                    print(f"\n✅ Successfully deleted {result['deleted_commits']} commit(s) from {repository}")
            elif result["status"] == "partial":
                if self.use_rich:
                    self.console.print(Panel(
                        f"[yellow]Deleted: {result['deleted_commits']}, Failed: {result['failed_commits']}[/yellow]\n"
                        f"[red]Error: {result['error_message']}[/red]",
                        title=f"[bold yellow]⚠️  {repository}[/bold yellow]",
                        border_style="yellow"
                    ))
                else:
                    print(f"\n⚠️  Partially completed for {repository}")
                    print(f"   Deleted: {result['deleted_commits']}, Failed: {result['failed_commits']}")
                    print(f"   Error: {result['error_message']}")
            else:
                if self.use_rich:
                    self.console.print(Panel(
                        f"[red]{result['error_message']}[/red]",
                        title=f"[bold red]❌ {repository}[/bold red]",
                        border_style="red"
                    ))
                else:
                    print(f"\n❌ Failed to process {repository}")
                    print(f"   Error: {result['error_message']}")

    def save_results(self, output_file: str = "deleted_commits.json") -> None:
        """Save deletion results to JSON file."""
        output_data = {
            "execution_date": datetime.now().isoformat(),
            "statistics": self.stats,
            "results": self.results,
            "skipped_for_later": self.skipped_for_later
        }

        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)

        if self.use_rich:
            self.console.print(f"\n[green]✓[/green] Results saved to [cyan]{output_file}[/cyan]")
        else:
            print(f"\n✓ Results saved to {output_file}")

        # Also save skipped commits to separate file for easy retry
        if self.skipped_for_later:
            skipped_file = "skipped_commits.json"
            with open(skipped_file, 'w') as f:
                json.dump({
                    "date": datetime.now().isoformat(),
                    "commits": self.skipped_for_later
                }, f, indent=2)
            if self.use_rich:
                self.console.print(f"[green]✓[/green] Skipped commits saved to [cyan]{skipped_file}[/cyan]")
            else:
                print(f"✓ Skipped commits saved to {skipped_file}")

    def print_summary(self) -> None:
        """Print execution summary."""
        if self.use_rich:
            summary_table = Table(title="Final Summary", box=box.DOUBLE, show_header=False)
            summary_table.add_column("Metric", style="cyan bold")
            summary_table.add_column("Value", style="green bold")

            summary_table.add_row("Total repositories", str(self.stats['total_repos']))
            summary_table.add_row("  - Processed", f"[green]{self.stats['processed_repos']}[/green]")
            summary_table.add_row("  - Skipped", f"[yellow]{self.stats['skipped_repos']}[/yellow]")
            summary_table.add_row("", "")
            summary_table.add_row("Total commits", str(self.stats['total_commits']))
            summary_table.add_row("  - Deleted", f"[green]{self.stats['deleted_commits']}[/green]")
            summary_table.add_row("  - Skipped for later", f"[yellow]{self.stats['skipped_commits']}[/yellow]")

            self.console.print()
            self.console.print(summary_table)
            self.console.print()
        else:
            print(f"\n{'='*70}")
            print("FINAL SUMMARY")
            print(f"{'='*70}")
            print(f"Total repositories:        {self.stats['total_repos']}")
            print(f"  - Processed:             {self.stats['processed_repos']}")
            print(f"  - Skipped:               {self.stats['skipped_repos']}")
            print(f"\nTotal commits:             {self.stats['total_commits']}")
            print(f"  - Deleted:               {self.stats['deleted_commits']}")
            print(f"  - Skipped for later:     {self.stats['skipped_commits']}")
            print(f"{'='*70}\n")


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="🗑️  GitHub Commit Deleter - Safely delete commits with human-in-loop confirmation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Delete commits from default file (commits.json)
  python undo_commits.py

  # Delete commits from skipped commits file
  python undo_commits.py --input skipped_commits.json

  # Use plain output (no colors/formatting)
  python undo_commits.py --no-rich

Environment Variables:
  GITHUB_TOKEN    GitHub personal access token (required)
        """
    )

    parser.add_argument(
        '--input', '-i',
        default='commits.json',
        help='Input JSON file containing commits to delete (default: commits.json)'
    )

    parser.add_argument(
        '--output', '-o',
        default='deleted_commits.json',
        help='Output JSON file for results (default: deleted_commits.json)'
    )

    parser.add_argument(
        '--no-rich',
        action='store_true',
        help='Disable rich formatting (use plain text output)'
    )

    args = parser.parse_args()

    # Load GitHub token from environment
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable not set")
        print("Please set your GitHub personal access token:")
        print("  export GITHUB_TOKEN='your_token_here'")
        return 1

    try:
        # Initialize deleter
        deleter = GitHubCommitDeleter(token, use_rich=not args.no_rich)

        # Check if git is installed
        if not deleter.check_git_installed():
            deleter.print("[red]Error: git is not installed or not in PATH[/red]" if deleter.use_rich else "Error: git is not installed or not in PATH")
            deleter.print("Please install git: https://git-scm.com/downloads")
            return 1

        if deleter.use_rich:
            deleter.console.print("[green]✓[/green] Git is installed and ready")
        else:
            print("✓ Git is installed and ready")

        # Load commits from file
        commits = deleter.load_commits_file(args.input)

        # Process all commits with human confirmation
        deleter.process_all_commits(commits)

        # Save results
        deleter.save_results(args.output)

        # Print summary
        deleter.print_summary()

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    except ValueError as e:
        print(f"Error: {e}")
        return 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user")
        print("Partial results may have been saved.")
        return 1

    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
