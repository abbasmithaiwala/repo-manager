#!/usr/bin/env python3
"""
GitHub Repository Description Manager
Fetch and update repository descriptions for all repos owned by the authenticated user.
"""

import os
import json
import argparse
from datetime import datetime
from typing import List, Dict, Optional

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
    print("⚠️  For better experience, install: pip install -r requirements.txt")
    print()


class GitHubDescriptionManager:
    """Manages repository descriptions for all user repos."""

    def __init__(self, token: str, use_rich: bool = True):
        """
        Initialize the manager with GitHub authentication.

        Args:
            token: GitHub personal access token
            use_rich: Use rich formatting (if available)
        """
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.use_rich = use_rich and RICH_AVAILABLE
        if self.use_rich:
            self.console = Console()

        self.repos = []
        self.updated_repos = []
        self.stats = {
            "total_repos": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0
        }

    def print(self, *args, **kwargs):
        """Print with rich if available, otherwise regular print."""
        if self.use_rich:
            self.console.print(*args, **kwargs)
        else:
            print(*args, **kwargs)

    def get_authenticated_user(self) -> Dict:
        """Get authenticated user information."""
        try:
            response = requests.get(f"{self.base_url}/user", headers=self.headers, timeout=30)

            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json()
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def fetch_all_repos(self, affiliation: str = "owner") -> List[Dict]:
        """
        Fetch all repositories for the authenticated user.

        Args:
            affiliation: Type of repos to fetch (owner, collaborator, organization_member)

        Returns:
            List of repository dictionaries
        """
        repos = []
        page = 1
        per_page = 100

        if self.use_rich:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
            ) as progress:
                task = progress.add_task("Fetching repositories...", total=None)

                while True:
                    try:
                        url = f"{self.base_url}/user/repos"
                        params = {
                            "affiliation": affiliation,
                            "per_page": per_page,
                            "page": page,
                            "sort": "updated"
                        }

                        response = requests.get(url, headers=self.headers, params=params, timeout=30)

                        if response.status_code != 200:
                            progress.update(task, description=f"[red]Error: HTTP {response.status_code}[/red]")
                            break

                        page_repos = response.json()

                        if not page_repos:
                            break

                        repos.extend(page_repos)
                        progress.update(task, description=f"Fetched {len(repos)} repositories...")

                        page += 1

                    except Exception as e:
                        progress.update(task, description=f"[red]Error: {str(e)}[/red]")
                        break

                progress.update(task, description=f"[green]✓ Fetched {len(repos)} repositories[/green]", completed=True)
        else:
            print("Fetching repositories...")
            while True:
                try:
                    url = f"{self.base_url}/user/repos"
                    params = {
                        "affiliation": affiliation,
                        "per_page": per_page,
                        "page": page,
                        "sort": "updated"
                    }

                    response = requests.get(url, headers=self.headers, params=params, timeout=30)

                    if response.status_code != 200:
                        print(f"Error: HTTP {response.status_code}")
                        break

                    page_repos = response.json()

                    if not page_repos:
                        break

                    repos.extend(page_repos)
                    print(f"Fetched {len(repos)} repositories...")

                    page += 1

                except Exception as e:
                    print(f"Error: {e}")
                    break

            print(f"✓ Fetched {len(repos)} repositories")

        # Store simplified repo info
        self.repos = [{
            "name": repo["name"],
            "full_name": repo["full_name"],
            "description": repo.get("description", ""),
            "private": repo["private"],
            "url": repo["html_url"],
            "updated_at": repo["updated_at"]
        } for repo in repos]

        self.stats["total_repos"] = len(self.repos)
        return self.repos

    def update_repo_description(self, full_name: str, description: str) -> tuple:
        """
        Update repository description.

        Args:
            full_name: Full repository name (owner/repo)
            description: New description to set

        Returns:
            Tuple of (success: bool, error_message: str)
        """
        url = f"{self.base_url}/repos/{full_name}"
        payload = {"description": description}

        try:
            response = requests.patch(url, headers=self.headers, json=payload, timeout=30)

            if response.status_code == 200:
                return (True, None)
            else:
                return (False, f"HTTP {response.status_code}: {response.text}")
        except Exception as e:
            return (False, str(e))

    def display_repos_table(self, repos: List[Dict], title: str = "Repositories") -> None:
        """Display repositories in a table."""
        if self.use_rich:
            table = Table(title=title, box=box.ROUNDED, show_lines=False)
            table.add_column("#", style="cyan", width=4)
            table.add_column("Repository", style="yellow", width=40)
            table.add_column("Description", style="white", width=50)
            table.add_column("Private", style="magenta", width=7)

            for idx, repo in enumerate(repos, 1):
                name = repo["full_name"]
                desc = repo["description"][:47] + "..." if repo["description"] and len(repo["description"]) > 50 else (repo["description"] or "(empty)")
                private = "Yes" if repo["private"] else "No"

                table.add_row(str(idx), name, desc, private)

            self.console.print()
            self.console.print(table)
            self.console.print()
        else:
            print(f"\n{'='*100}")
            print(f"{title}")
            print(f"{'='*100}")
            for idx, repo in enumerate(repos, 1):
                desc = repo["description"] or "(empty)"
                private = "Private" if repo["private"] else "Public"
                print(f"{idx}. {repo['full_name']}")
                print(f"   Description: {desc}")
                print(f"   {private}")
                print()

    def bulk_update_all(self, description: str) -> None:
        """
        Update all repositories with the same description.

        Args:
            description: Description to set for all repos
        """
        if self.use_rich:
            self.console.print(Panel(
                f"[bold yellow]Updating {len(self.repos)} repositories[/bold yellow]\n"
                f"[dim]New description: {description or '(empty)'}[/dim]",
                title="[bold]Bulk Update[/bold]",
                border_style="yellow"
            ))
        else:
            print(f"\n{'='*70}")
            print(f"Bulk Update: {len(self.repos)} repositories")
            print(f"New description: {description or '(empty)'}")
            print(f"{'='*70}\n")

        for idx, repo in enumerate(self.repos, 1):
            full_name = repo["full_name"]

            self.print(f"[{idx}/{len(self.repos)}] [cyan]{full_name}[/cyan]..." if self.use_rich else f"[{idx}/{len(self.repos)}] {full_name}...")

            success, error = self.update_repo_description(full_name, description)

            if success:
                self.stats["updated"] += 1
                self.updated_repos.append({
                    "repository": full_name,
                    "old_description": repo["description"],
                    "new_description": description,
                    "status": "success"
                })
                self.print(f"  [green]✓ Updated[/green]" if self.use_rich else f"  ✓ Updated")
            else:
                self.stats["failed"] += 1
                self.updated_repos.append({
                    "repository": full_name,
                    "old_description": repo["description"],
                    "new_description": description,
                    "status": "failed",
                    "error": error
                })
                self.print(f"  [red]✗ Failed: {error}[/red]" if self.use_rich else f"  ✗ Failed: {error}")

    def interactive_update(self) -> None:
        """Interactively update repository descriptions."""
        if not self.repos:
            self.print("[yellow]No repositories found[/yellow]" if self.use_rich else "No repositories found")
            return

        # Display repos
        self.display_repos_table(self.repos)

        if self.use_rich:
            try:
                # Ask what to do
                action = questionary.select(
                    "What would you like to do?",
                    choices=[
                        questionary.Choice("🧹 Clear all descriptions (set to empty)", value="clear_all"),
                        questionary.Choice("✏️  Set all to same custom description", value="set_all"),
                        questionary.Choice("🎯 Select specific repos to update", value="select"),
                        questionary.Choice("💾 Export current descriptions to JSON", value="export"),
                        questionary.Choice("❌ Exit without changes", value="exit"),
                    ],
                    style=questionary.Style([
                        ('selected', 'bold'),
                        ('pointer', 'cyan bold'),
                    ])
                ).ask()

                if action == "clear_all":
                    confirm = questionary.confirm(
                        f"Clear descriptions for all {len(self.repos)} repositories?",
                        default=False
                    ).ask()

                    if confirm:
                        self.bulk_update_all("")
                    else:
                        self.print("[yellow]Cancelled[/yellow]")

                elif action == "set_all":
                    new_desc = questionary.text(
                        "Enter description for all repositories:",
                        validate=lambda text: True
                    ).ask()

                    if new_desc is not None:
                        confirm = questionary.confirm(
                            f"Set description for all {len(self.repos)} repositories to: '{new_desc}'?",
                            default=False
                        ).ask()

                        if confirm:
                            self.bulk_update_all(new_desc)
                        else:
                            self.print("[yellow]Cancelled[/yellow]")

                elif action == "select":
                    self.print("[yellow]Feature coming soon: Select specific repos[/yellow]")
                    # Could implement checkbox selection here

                elif action == "export":
                    self.export_descriptions()

                elif action == "exit":
                    self.print("[yellow]Exiting without changes[/yellow]")

            except (KeyboardInterrupt, EOFError):
                self.print("\n[yellow]Operation cancelled by user[/yellow]")

        else:
            # Fallback text-based interaction
            print("\nOptions:")
            print("1. Clear all descriptions (set to empty)")
            print("2. Set all to same custom description")
            print("3. Export current descriptions to JSON")
            print("4. Exit without changes")

            choice = input("\nEnter choice (1-4): ").strip()

            if choice == "1":
                confirm = input(f"Clear descriptions for all {len(self.repos)} repositories? (yes/no): ").strip().lower()
                if confirm in ['yes', 'y']:
                    self.bulk_update_all("")

            elif choice == "2":
                new_desc = input("Enter description for all repositories: ").strip()
                confirm = input(f"Set description for all {len(self.repos)} repositories? (yes/no): ").strip().lower()
                if confirm in ['yes', 'y']:
                    self.bulk_update_all(new_desc)

            elif choice == "3":
                self.export_descriptions()

            elif choice == "4":
                print("Exiting without changes")

    def export_descriptions(self, filename: str = "repo_descriptions.json") -> None:
        """Export current repository descriptions to JSON file."""
        data = {
            "exported_at": datetime.now().isoformat(),
            "total_repositories": len(self.repos),
            "repositories": self.repos
        }

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

        self.print(f"[green]✓[/green] Exported to [cyan]{filename}[/cyan]" if self.use_rich else f"✓ Exported to {filename}")

    def save_results(self, filename: str = "description_updates.json") -> None:
        """Save update results to JSON file."""
        if not self.updated_repos:
            return

        data = {
            "updated_at": datetime.now().isoformat(),
            "statistics": self.stats,
            "updates": self.updated_repos
        }

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

        self.print(f"\n[green]✓[/green] Results saved to [cyan]{filename}[/cyan]" if self.use_rich else f"\n✓ Results saved to {filename}")

    def print_summary(self) -> None:
        """Print summary of operations."""
        if self.stats["updated"] == 0 and self.stats["failed"] == 0:
            return

        if self.use_rich:
            summary_table = Table(title="Summary", box=box.DOUBLE, show_header=False)
            summary_table.add_column("Metric", style="cyan bold")
            summary_table.add_column("Value", style="green bold")

            summary_table.add_row("Total repositories", str(self.stats['total_repos']))
            summary_table.add_row("Updated", f"[green]{self.stats['updated']}[/green]")
            summary_table.add_row("Failed", f"[red]{self.stats['failed']}[/red]")
            summary_table.add_row("Skipped", f"[yellow]{self.stats['skipped']}[/yellow]")

            self.console.print()
            self.console.print(summary_table)
            self.console.print()
        else:
            print(f"\n{'='*70}")
            print("SUMMARY")
            print(f"{'='*70}")
            print(f"Total repositories: {self.stats['total_repos']}")
            print(f"Updated:            {self.stats['updated']}")
            print(f"Failed:             {self.stats['failed']}")
            print(f"Skipped:            {self.stats['skipped']}")
            print(f"{'='*70}\n")


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="📝 GitHub Repository Description Manager - Manage descriptions for all your repos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (recommended)
  python update_descriptions.py

  # Clear all descriptions
  python update_descriptions.py --clear

  # Set all descriptions to custom text
  python update_descriptions.py --set "My awesome projects"

  # Export current descriptions
  python update_descriptions.py --export

  # Use plain output (no colors/formatting)
  python update_descriptions.py --no-rich

Environment Variables:
  GITHUB_TOKEN    GitHub personal access token (required)
        """
    )

    parser.add_argument(
        '--clear',
        action='store_true',
        help='Clear all repository descriptions (set to empty)'
    )

    parser.add_argument(
        '--set',
        type=str,
        metavar='DESCRIPTION',
        help='Set all repositories to this description'
    )

    parser.add_argument(
        '--export',
        action='store_true',
        help='Export current descriptions to JSON file'
    )

    parser.add_argument(
        '--no-rich',
        action='store_true',
        help='Disable rich formatting (use plain text output)'
    )

    parser.add_argument(
        '--affiliation',
        choices=['owner', 'collaborator', 'organization_member'],
        default='owner',
        help='Type of repositories to fetch (default: owner)'
    )

    args = parser.parse_args()

    # Load GitHub token
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable not set")
        print("Please set your GitHub personal access token:")
        print("  export GITHUB_TOKEN='your_token_here'")
        return 1

    try:
        # Initialize manager
        manager = GitHubDescriptionManager(token, use_rich=not args.no_rich)

        # Get authenticated user
        user_info = manager.get_authenticated_user()
        if not user_info["success"]:
            manager.print(f"[red]Error: {user_info['error']}[/red]" if manager.use_rich else f"Error: {user_info['error']}")
            return 1

        username = user_info["data"]["login"]

        if manager.use_rich:
            manager.console.print(Panel.fit(
                f"[bold green]✓[/bold green] Authenticated as [bold cyan]{username}[/bold cyan]",
                border_style="green"
            ))
        else:
            print(f"✓ Authenticated as {username}\n")

        # Fetch repositories
        repos = manager.fetch_all_repos(affiliation=args.affiliation)

        if not repos:
            manager.print("[yellow]No repositories found[/yellow]" if manager.use_rich else "No repositories found")
            return 0

        # Handle command-line modes
        if args.export:
            manager.export_descriptions()
            return 0

        if args.clear:
            manager.display_repos_table(repos)

            if manager.use_rich:
                confirm = questionary.confirm(
                    f"Clear descriptions for all {len(repos)} repositories?",
                    default=False
                ).ask()
            else:
                confirm_input = input(f"Clear descriptions for all {len(repos)} repositories? (yes/no): ").strip().lower()
                confirm = confirm_input in ['yes', 'y']

            if confirm:
                manager.bulk_update_all("")
                manager.save_results()
                manager.print_summary()
            else:
                manager.print("[yellow]Cancelled[/yellow]" if manager.use_rich else "Cancelled")

            return 0

        if args.set:
            manager.display_repos_table(repos)

            if manager.use_rich:
                confirm = questionary.confirm(
                    f"Set description for all {len(repos)} repositories to: '{args.set}'?",
                    default=False
                ).ask()
            else:
                confirm_input = input(f"Set description for all {len(repos)} repositories? (yes/no): ").strip().lower()
                confirm = confirm_input in ['yes', 'y']

            if confirm:
                manager.bulk_update_all(args.set)
                manager.save_results()
                manager.print_summary()
            else:
                manager.print("[yellow]Cancelled[/yellow]" if manager.use_rich else "Cancelled")

            return 0

        # Interactive mode (default)
        manager.interactive_update()

        if manager.updated_repos:
            manager.save_results()
            manager.print_summary()

        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user")
        return 1

    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
