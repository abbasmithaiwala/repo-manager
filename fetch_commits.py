#!/usr/bin/env python3
"""
GitHub Commit Fetcher
Fetches all commits made by the authenticated user on a specific date across ALL repositories.
This includes commits to owned repos, forks, and any other repository across GitHub.
Uses GitHub Search API for comprehensive commit discovery.
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Set
import requests
import time


class GitHubCommitFetcher:
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.base_url = 'https://api.github.com'
        self.username = None

    def get_authenticated_user(self) -> Dict:
        """Get the authenticated user's information."""
        response = requests.get(f'{self.base_url}/user', headers=self.headers)
        response.raise_for_status()
        user_data = response.json()
        return {
            'login': user_data['login'],
            'email': user_data.get('email'),
            'name': user_data.get('name')
        }

    def search_commits_by_author_and_date(self, author: str, date: str) -> List[Dict]:
        """
        Use GitHub Search API to find commits by author on a specific date.
        This searches across ALL of GitHub, including forks and any repository.
        """
        target_date = datetime.strptime(date, '%Y-%m-%d')
        next_date = target_date + timedelta(days=1)

        # GitHub Search API date format
        date_str = target_date.strftime('%Y-%m-%d')
        next_date_str = next_date.strftime('%Y-%m-%d')

        # Search query: author and date range
        query = f'author:{author} committer-date:{date_str}..{next_date_str}'

        print(f"Searching commits for author '{author}' on {date}...")
        print(f"Search query: {query}\n")

        all_commits = []
        page = 1
        per_page = 100

        while True:
            try:
                response = requests.get(
                    f'{self.base_url}/search/commits',
                    headers={
                        **self.headers,
                        'Accept': 'application/vnd.github.cloak-preview+json'  # Required for commit search
                    },
                    params={
                        'q': query,
                        'per_page': per_page,
                        'page': page,
                        'sort': 'committer-date',
                        'order': 'desc'
                    }
                )

                # Check rate limiting
                if response.status_code == 403:
                    reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                    if reset_time:
                        wait_time = reset_time - int(time.time())
                        print(f"Rate limit reached. Waiting {wait_time} seconds...")
                        time.sleep(wait_time + 1)
                        continue

                response.raise_for_status()
                data = response.json()

                items = data.get('items', [])
                if not items:
                    break

                print(f"  Page {page}: Found {len(items)} commits")
                all_commits.extend(items)

                # Check if there are more pages
                total_count = data.get('total_count', 0)
                if len(all_commits) >= total_count or len(items) < per_page:
                    break

                page += 1
                time.sleep(0.5)  # Be nice to the API

            except requests.exceptions.HTTPError as e:
                print(f"Error searching commits: {e}")
                if e.response.status_code == 422:
                    print("Search query may be invalid or no results found")
                break

        print(f"Total commits found: {len(all_commits)}\n")
        return all_commits

    def fetch_commits_by_date(self, date: str) -> List[Dict]:
        """
        Fetch all commits made by the user on a specific date.
        Uses GitHub Search API to find commits across ALL repositories.
        """
        # Validate date format
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format")

        # Get authenticated user info
        user_info = self.get_authenticated_user()
        self.username = user_info['login']

        print(f"Authenticated as: {self.username}")
        if user_info.get('name'):
            print(f"Name: {user_info['name']}")
        if user_info.get('email'):
            print(f"Email: {user_info['email']}")
        print()

        # Search for commits using the Search API
        search_results = self.search_commits_by_author_and_date(self.username, date)

        # Process and format the results
        formatted_commits = []
        for commit_data in search_results:
            repo_name = commit_data['repository']['full_name']
            commit = commit_data['commit']
            sha = commit_data['sha']

            formatted_commit = {
                'repository': repo_name,
                'commit_id': sha,
                'commit_message': commit['message'],
                'timestamp': commit['author']['date'],
                'url': commit_data['html_url'],
                'author_name': commit['author']['name'],
                'author_email': commit['author']['email'],
                'committer_name': commit['committer']['name'],
                'committer_date': commit['committer']['date']
            }
            formatted_commits.append(formatted_commit)

            print(f"  [{repo_name}] {sha[:7]}")

        return formatted_commits


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
                print(f"    Author: {commit.get('author_name', 'N/A')} <{commit.get('author_email', 'N/A')}>")
                print()
        else:
            print("\nNo commits found for the specified date.")
            print("Make sure the date is correct and that you have commits on that date.")

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
