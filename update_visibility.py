#!/usr/bin/env python3
"""
GitHub Repository Visibility Manager
Makes repositories private/public with human-in-the-loop confirmation.
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import List, Dict, Optional, Tuple

try:
    import requests
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich import box
    import questionary
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Warning: 'rich' and 'questionary' not installed. Install with: pip install -r requirements.txt")
    print("Running in plain text mode...")


class RepositoryVisibilityManager:
    """Manages repository visibility settings on GitHub."""

    def __init__(self, use_rich: bool = True):
        """Initialize the visibility manager."""
        self.token = os.environ.get("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GITHUB_TOKEN environment variable not set")

        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }

        self.use_rich = use_rich and RICH_AVAILABLE
        self.console = Console() if self.use_rich else None

        self.repos: List[Dict] = []
        self.updated_repos: List[Dict] = []
        self.skipped_repos: List[Dict] = []

        self.stats = {
            "total_repos": 0,
            "private_repos": 0,
            "public_repos": 0,
            "updated_to_private": 0,
            "updated_to_public": 0,
            "skipped": 0,
            "errors": 0
        }

    def print_message(self, message: str, style: str = ""):
        """Print message with optional rich formatting."""
        if self.use_rich:
            self.console.print(message, style=style)
        else:
            print(message)

    def fetch_all_repos(self, affiliation: str = "owner") -> List[Dict]:
        """Fetch all repositories for the authenticated user."""
        repos = []
        page = 1
        per_page = 100

        if self.use_rich:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                task = progress.add_task("Fetching repositories...", total=None)

                while True:
                    url = f"{self.base_url}/user/repos"
                    params = {
                        "affiliation": affiliation,
                        "per_page": per_page,
                        "page": page,
                        "sort": "updated"
                    }

                    try:
                        response = requests.get(url, headers=self.headers, params=params, timeout=30)
                        response.raise_for_status()

                        page_repos = response.json()
                        if not page_repos:
                            break

                        repos.extend(page_repos)
                        progress.update(task, description=f"Fetching repositories... (found {len(repos)})")
                        page += 1

                    except requests.exceptions.RequestException as e:
                        progress.update(task, description=f"[red]Error fetching repos: {e}[/red]")
                        break
        else:
            print("Fetching repositories...")
            while True:
                url = f"{self.base_url}/user/repos"
                params = {
                    "affiliation": affiliation,
                    "per_page": per_page,
                    "page": page,
                    "sort": "updated"
                }

                try:
                    response = requests.get(url, headers=self.headers, params=params, timeout=30)
                    response.raise_for_status()

                    page_repos = response.json()
                    if not page_repos:
                        break

                    repos.extend(page_repos)
                    print(f"Found {len(repos)} repositories...")
                    page += 1

                except requests.exceptions.RequestException as e:
                    print(f"Error fetching repos: {e}")
                    break

        return repos

    def update_repo_visibility(self, full_name: str, private: bool) -> Tuple[bool, Optional[str]]:
        """Update repository visibility."""
        url = f"{self.base_url}/repos/{full_name}"
        payload = {"private": private}

        try:
            response = requests.patch(url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()

            return (True, None)

        except requests.exceptions.RequestException as e:
            error_msg = f"HTTP {response.status_code}" if hasattr(e, 'response') else str(e)
            return (False, error_msg)

    def display_repos_table(self) -> None:
        """Display repositories in a formatted table."""
        if self.use_rich:
            table = Table(title="Your Repositories", box=box.ROUNDED, show_lines=True)
            table.add_column("#", style="cyan", width=4)
            table.add_column("Repository", style="blue", width=40)
            table.add_column("Visibility", style="yellow", width=12)
            table.add_column("Stars", style="magenta", width=8)
            table.add_column("Forks", style="green", width=8)
            table.add_column("Updated", style="white", width=20)

            for idx, repo in enumerate(self.repos, 1):
                visibility = "🔒 Private" if repo["private"] else "🌍 Public"
                visibility_style = "green" if repo["private"] else "yellow"

                table.add_row(
                    str(idx),
                    repo["full_name"],
                    f"[{visibility_style}]{visibility}[/{visibility_style}]",
                    str(repo["stargazers_count"]),
                    str(repo["forks_count"]),
                    repo["updated_at"][:10]
                )

            self.console.print(table)
        else:
            print("\n" + "="*80)
            print(f"{'#':<4} {'Repository':<40} {'Visibility':<12} {'Stars':<8} {'Forks':<8}")
            print("="*80)

            for idx, repo in enumerate(self.repos, 1):
                visibility = "Private" if repo["private"] else "Public"
                print(f"{idx:<4} {repo['full_name']:<40} {visibility:<12} {repo['stargazers_count']:<8} {repo['forks_count']:<8}")

            print("="*80 + "\n")

    def interactive_update(self) -> None:
        """Interactively update repository visibility."""
        if self.use_rich:
            action = questionary.select(
                "What would you like to do?",
                choices=[
                    questionary.Choice("🔒 Make all repositories private", value="all_private"),
                    questionary.Choice("🌍 Make all repositories public", value="all_public"),
                    questionary.Choice("🎯 Review each repository individually", value="individual"),
                    questionary.Choice("💾 Export visibility status to JSON", value="export"),
                    questionary.Choice("❌ Exit without changes", value="exit"),
                ],
                style=questionary.Style([
                    ('selected', 'bold'),
                    ('pointer', 'cyan bold'),
                ])
            ).ask()
        else:
            print("\nWhat would you like to do?")
            print("1. Make all repositories private")
            print("2. Make all repositories public")
            print("3. Review each repository individually")
            print("4. Export visibility status to JSON")
            print("5. Exit without changes")
            action_map = {"1": "all_private", "2": "all_public", "3": "individual", "4": "export", "5": "exit"}
            choice = input("Enter your choice (1-5): ").strip()
            action = action_map.get(choice, "exit")

        if action == "exit":
            self.print_message("\n[yellow]Exiting without changes.[/yellow]", style="yellow")
            return

        elif action == "export":
            self.export_visibility_status()
            return

        elif action == "all_private":
            if self.use_rich:
                confirm = questionary.confirm(
                    f"Are you sure you want to make ALL {len(self.repos)} repositories private?",
                    default=False
                ).ask()
            else:
                confirm = input(f"Are you sure you want to make ALL {len(self.repos)} repositories private? (y/N): ").strip().lower() == 'y'

            if confirm:
                self.bulk_update_all(private=True)
            else:
                self.print_message("[yellow]Operation cancelled.[/yellow]", style="yellow")

        elif action == "all_public":
            if self.use_rich:
                self.console.print(Panel.fit(
                    "[bold red]⚠️  WARNING ⚠️[/bold red]\n\n"
                    "Making repositories public will make all code visible to everyone!\n"
                    "This cannot be easily undone for private repositories.",
                    border_style="red"
                ))
                confirm = questionary.confirm(
                    f"Are you ABSOLUTELY sure you want to make ALL {len(self.repos)} repositories PUBLIC?",
                    default=False
                ).ask()
            else:
                print("\n" + "="*80)
                print("WARNING: Making repositories public will make all code visible to everyone!")
                print("This cannot be easily undone for private repositories.")
                print("="*80)
                confirm = input(f"Are you ABSOLUTELY sure you want to make ALL {len(self.repos)} repositories PUBLIC? (y/N): ").strip().lower() == 'y'

            if confirm:
                self.bulk_update_all(private=False)
            else:
                self.print_message("[yellow]Operation cancelled.[/yellow]", style="yellow")

        elif action == "individual":
            self.review_individually()

    def bulk_update_all(self, private: bool) -> None:
        """Update all repositories to the same visibility."""
        action_text = "private" if private else "public"

        if self.use_rich:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                task = progress.add_task(f"Making repositories {action_text}...", total=len(self.repos))

                for idx, repo in enumerate(self.repos, 1):
                    full_name = repo["full_name"]
                    current_private = repo["private"]

                    # Skip if already in desired state
                    if current_private == private:
                        progress.update(task, advance=1, description=f"[dim]Skipping {full_name} (already {action_text})[/dim]")
                        self.stats["skipped"] += 1
                        continue

                    progress.update(task, description=f"Updating {full_name}...")

                    success, error = self.update_repo_visibility(full_name, private)

                    if success:
                        self.stats["updated_to_private" if private else "updated_to_public"] += 1
                        self.updated_repos.append({
                            "repository": full_name,
                            "old_visibility": "private" if current_private else "public",
                            "new_visibility": action_text,
                            "status": "success"
                        })
                        progress.update(task, advance=1, description=f"[green]✓[/green] Updated {full_name}")
                    else:
                        self.stats["errors"] += 1
                        self.updated_repos.append({
                            "repository": full_name,
                            "old_visibility": "private" if current_private else "public",
                            "new_visibility": action_text,
                            "status": "error",
                            "error": error
                        })
                        progress.update(task, advance=1, description=f"[red]✗[/red] Failed {full_name}: {error}")
        else:
            for idx, repo in enumerate(self.repos, 1):
                full_name = repo["full_name"]
                current_private = repo["private"]

                if current_private == private:
                    print(f"[{idx}/{len(self.repos)}] Skipping {full_name} (already {action_text})")
                    self.stats["skipped"] += 1
                    continue

                print(f"[{idx}/{len(self.repos)}] Updating {full_name}...")

                success, error = self.update_repo_visibility(full_name, private)

                if success:
                    self.stats["updated_to_private" if private else "updated_to_public"] += 1
                    self.updated_repos.append({
                        "repository": full_name,
                        "old_visibility": "private" if current_private else "public",
                        "new_visibility": action_text,
                        "status": "success"
                    })
                    print(f"  ✓ Success")
                else:
                    self.stats["errors"] += 1
                    self.updated_repos.append({
                        "repository": full_name,
                        "old_visibility": "private" if current_private else "public",
                        "new_visibility": action_text,
                        "status": "error",
                        "error": error
                    })
                    print(f"  ✗ Failed: {error}")

        self.save_results()
        self.display_summary()

    def review_individually(self) -> None:
        """Review and update each repository individually."""
        for idx, repo in enumerate(self.repos, 1):
            full_name = repo["full_name"]
            current_private = repo["private"]
            current_visibility = "🔒 Private" if current_private else "🌍 Public"
            repo_url = repo["html_url"]

            if self.use_rich:
                # Display repository info
                self.console.print("\n" + "="*80)
                self.console.print(Panel.fit(
                    f"[bold cyan]{full_name}[/bold cyan]\n"
                    f"[dim]{repo_url}[/dim]\n\n"
                    f"Current: {current_visibility}\n"
                    f"Stars: ⭐ {repo['stargazers_count']} | Forks: 🍴 {repo['forks_count']} | "
                    f"Updated: 📅 {repo['updated_at'][:10]}",
                    title=f"[bold]Repository {idx}/{len(self.repos)}[/bold]",
                    border_style="cyan"
                ))

                # Ask what to do
                choices = []
                if current_private:
                    choices.append(questionary.Choice("🌍 Make Public", value="public"))
                    choices.append(questionary.Choice("🔒 Keep Private", value="skip"))
                else:
                    choices.append(questionary.Choice("🔒 Make Private", value="private"))
                    choices.append(questionary.Choice("🌍 Keep Public", value="skip"))

                choices.append(questionary.Choice("⏭️  Skip All Remaining", value="skip_all"))

                action = questionary.select(
                    f"What would you like to do with {full_name}?",
                    choices=choices,
                    style=questionary.Style([
                        ('selected', 'bold'),
                        ('pointer', 'cyan bold'),
                    ])
                ).ask()
            else:
                print("\n" + "="*80)
                print(f"Repository {idx}/{len(self.repos)}: {full_name}")
                print(f"URL: {repo_url}")
                print(f"Current: {current_visibility}")
                print(f"Stars: {repo['stargazers_count']} | Forks: {repo['forks_count']} | Updated: {repo['updated_at'][:10]}")
                print("="*80)

                if current_private:
                    print("1. Make Public")
                    print("2. Keep Private")
                else:
                    print("1. Make Private")
                    print("2. Keep Public")
                print("3. Skip All Remaining")

                choice = input("Enter your choice (1-3): ").strip()
                action_map = {
                    "1": "public" if current_private else "private",
                    "2": "skip",
                    "3": "skip_all"
                }
                action = action_map.get(choice, "skip")

            if action == "skip_all":
                self.print_message(f"\n[yellow]Skipping all remaining {len(self.repos) - idx + 1} repositories.[/yellow]", style="yellow")
                break

            elif action == "skip":
                self.stats["skipped"] += 1
                self.skipped_repos.append({
                    "repository": full_name,
                    "current_visibility": "private" if current_private else "public",
                    "reason": "User chose to skip"
                })
                continue

            elif action in ["private", "public"]:
                new_private = (action == "private")

                success, error = self.update_repo_visibility(full_name, new_private)

                if success:
                    self.stats["updated_to_private" if new_private else "updated_to_public"] += 1
                    self.updated_repos.append({
                        "repository": full_name,
                        "old_visibility": "private" if current_private else "public",
                        "new_visibility": action,
                        "status": "success"
                    })
                    self.print_message(f"[green]✓ Successfully updated to {action}[/green]", style="green")
                else:
                    self.stats["errors"] += 1
                    self.updated_repos.append({
                        "repository": full_name,
                        "old_visibility": "private" if current_private else "public",
                        "new_visibility": action,
                        "status": "error",
                        "error": error
                    })
                    self.print_message(f"[red]✗ Failed to update: {error}[/red]", style="red")

        self.save_results()
        self.display_summary()

    def export_visibility_status(self, filename: str = "repo_visibility.json") -> None:
        """Export current visibility status to JSON."""
        export_data = {
            "export_date": datetime.now().isoformat(),
            "total_repos": len(self.repos),
            "repositories": [
                {
                    "name": repo["full_name"],
                    "visibility": "private" if repo["private"] else "public",
                    "stars": repo["stargazers_count"],
                    "forks": repo["forks_count"],
                    "url": repo["html_url"],
                    "updated_at": repo["updated_at"]
                }
                for repo in self.repos
            ]
        }

        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)

        self.print_message(f"\n[green]✓ Exported visibility status to {filename}[/green]", style="green")

    def save_results(self, filename: str = "visibility_updates.json") -> None:
        """Save update results to JSON file."""
        results = {
            "execution_date": datetime.now().isoformat(),
            "statistics": self.stats,
            "updated_repos": self.updated_repos,
            "skipped_repos": self.skipped_repos
        }

        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)

        self.print_message(f"\n[green]Results saved to {filename}[/green]", style="green")

    def display_summary(self) -> None:
        """Display final summary of operations."""
        if self.use_rich:
            self.console.print("\n" + "="*80)
            summary_panel = Panel.fit(
                f"[bold]Total Repositories:[/bold] {self.stats['total_repos']}\n"
                f"[green]Updated to Private:[/green] {self.stats['updated_to_private']}\n"
                f"[yellow]Updated to Public:[/yellow] {self.stats['updated_to_public']}\n"
                f"[dim]Skipped:[/dim] {self.stats['skipped']}\n"
                f"[red]Errors:[/red] {self.stats['errors']}",
                title="[bold]Summary[/bold]",
                border_style="green"
            )
            self.console.print(summary_panel)
        else:
            print("\n" + "="*80)
            print("SUMMARY")
            print("="*80)
            print(f"Total Repositories: {self.stats['total_repos']}")
            print(f"Updated to Private: {self.stats['updated_to_private']}")
            print(f"Updated to Public: {self.stats['updated_to_public']}")
            print(f"Skipped: {self.stats['skipped']}")
            print(f"Errors: {self.stats['errors']}")
            print("="*80)

    def run(self, mode: str = "interactive") -> None:
        """Run the visibility manager."""
        # Fetch repositories
        self.repos = self.fetch_all_repos()

        if not self.repos:
            self.print_message("[red]No repositories found.[/red]", style="red")
            return

        # Calculate stats
        self.stats["total_repos"] = len(self.repos)
        self.stats["private_repos"] = sum(1 for r in self.repos if r["private"])
        self.stats["public_repos"] = sum(1 for r in self.repos if not r["private"])

        # Display repos
        self.print_message(f"\n[bold cyan]Found {len(self.repos)} repositories[/bold cyan]", style="bold cyan")
        self.print_message(f"[green]Private: {self.stats['private_repos']}[/green] | [yellow]Public: {self.stats['public_repos']}[/yellow]\n")

        self.display_repos_table()

        # Execute based on mode
        if mode == "interactive":
            self.interactive_update()
        elif mode == "all_private":
            self.bulk_update_all(private=True)
        elif mode == "all_public":
            self.bulk_update_all(private=False)
        elif mode == "export":
            self.export_visibility_status()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Manage GitHub repository visibility settings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python update_visibility.py                    # Interactive mode
  python update_visibility.py --all-private      # Make all repos private
  python update_visibility.py --export           # Export visibility status
  python update_visibility.py --no-rich          # Disable rich formatting
        """
    )

    parser.add_argument('--all-private', action='store_true',
                       help='Make all repositories private')
    parser.add_argument('--all-public', action='store_true',
                       help='Make all repositories public (use with caution!)')
    parser.add_argument('--export', action='store_true',
                       help='Export current visibility status to JSON')
    parser.add_argument('--output', '-o', default='visibility_updates.json',
                       help='Output JSON file for results (default: visibility_updates.json)')
    parser.add_argument('--no-rich', action='store_true',
                       help='Disable rich formatting (plain text mode)')

    args = parser.parse_args()

    try:
        manager = RepositoryVisibilityManager(use_rich=not args.no_rich)

        if args.export:
            manager.repos = manager.fetch_all_repos()
            manager.export_visibility_status()
        elif args.all_private:
            manager.run(mode="all_private")
        elif args.all_public:
            manager.run(mode="all_public")
        else:
            manager.run(mode="interactive")

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
