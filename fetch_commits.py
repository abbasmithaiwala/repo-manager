#!/usr/bin/env python3
"""
GitHub Commit Fetcher
Fetches all commits made by the authenticated user on a specific date across all repositories.
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from typing import List, Dict
import requests


class GitHubCommitFetcher:
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.base_url = 'https://api.github.com'
        self.username = None

    def get_authenticated_user(self) -> str:
        """Get the authenticated user's username."""
        response = requests.get(f'{self.base_url}/user', headers=self.headers)
        response.raise_for_status()
        return response.json()['login']

    def get_all_repos(self) -> List[Dict]:
        """Fetch all repositories for the authenticated user."""
        repos = []
        page = 1
        per_page = 100

        print(f"Fetching repositories for user: {self.username}")

        while True:
            response = requests.get(
                f'{self.base_url}/user/repos',
                headers=self.headers,
                params={'page': page, 'per_page': per_page, 'affiliation': 'owner,collaborator,organization_member'}
            )
            response.raise_for_status()

            data = response.json()
            if not data:
                break

            repos.extend(data)
            print(f"  Found {len(repos)} repositories so far...")
            page += 1

        print(f"Total repositories: {len(repos)}")
        return repos

    def get_commits_for_date(self, repo_full_name: str, date: str) -> List[Dict]:
        """Fetch commits for a specific repository on a given date."""
        # Parse the date and create a range for the entire day
        target_date = datetime.strptime(date, '%Y-%m-%d')
        since = target_date.isoformat() + 'Z'
        until = (target_date + timedelta(days=1)).isoformat() + 'Z'

        commits = []
        page = 1
        per_page = 100

        while True:
            response = requests.get(
                f'{self.base_url}/repos/{repo_full_name}/commits',
                headers=self.headers,
                params={
                    'author': self.username,
                    'since': since,
                    'until': until,
                    'page': page,
                    'per_page': per_page
                }
            )

            if response.status_code == 409:
                # Repository is empty
                break

            response.raise_for_status()

            data = response.json()
            if not data:
                break

            commits.extend(data)
            page += 1

        return commits

    def fetch_commits_by_date(self, date: str) -> List[Dict]:
        """Fetch all commits made by the user on a specific date."""
        # Validate date format
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format")

        # Get authenticated user
        self.username = self.get_authenticated_user()

        # Get all repositories
        repos = self.get_all_repos()

        # Fetch commits from each repository
        all_commits = []
        print(f"\nSearching for commits on {date}...")

        for i, repo in enumerate(repos, 1):
            repo_name = repo['full_name']
            print(f"[{i}/{len(repos)}] Checking {repo_name}...", end=' ')

            try:
                commits = self.get_commits_for_date(repo_name, date)

                for commit in commits:
                    commit_data = {
                        'repository': repo_name,
                        'commit_id': commit['sha'],
                        'commit_message': commit['commit']['message'],
                        'timestamp': commit['commit']['author']['date'],
                        'url': commit['html_url']
                    }
                    all_commits.append(commit_data)

                if commits:
                    print(f"Found {len(commits)} commit(s)")
                else:
                    print("No commits")

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 409:
                    print("Empty repository")
                else:
                    print(f"Error: {e}")

        return all_commits


def main():
    parser = argparse.ArgumentParser(
        description='Fetch GitHub commits for a specific date',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python fetch_commits.py 2024-11-26
  python fetch_commits.py 2024-11-26 --output my_commits.json
        '''
    )
    parser.add_argument('date', help='Date in YYYY-MM-DD format')
    parser.add_argument('--output', '-o', default='commits.json', help='Output JSON file (default: commits.json)')

    args = parser.parse_args()

    # Get GitHub token from environment
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("Error: GITHUB_TOKEN environment variable not set")
        print("Please set it using: export GITHUB_TOKEN='your_token_here'")
        sys.exit(1)

    try:
        # Fetch commits
        fetcher = GitHubCommitFetcher(token)
        commits = fetcher.fetch_commits_by_date(args.date)

        # Save to JSON file
        with open(args.output, 'w') as f:
            json.dump({
                'date': args.date,
                'total_commits': len(commits),
                'commits': commits
            }, f, indent=2)

        print(f"\n{'='*60}")
        print(f"Summary:")
        print(f"  Date: {args.date}")
        print(f"  Total commits found: {len(commits)}")
        print(f"  Output file: {args.output}")
        print(f"{'='*60}")

        if commits:
            print("\nCommits:")
            for commit in commits:
                print(f"  [{commit['repository']}]")
                print(f"    ID: {commit['commit_id'][:7]}")
                print(f"    Message: {commit['commit_message'].split(chr(10))[0][:80]}")
                print(f"    Time: {commit['timestamp']}")
                print()

    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"GitHub API Error: {e}")
        if e.response.status_code == 401:
            print("Check that your GITHUB_TOKEN is valid")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
