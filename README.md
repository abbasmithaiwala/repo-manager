# GitHub Repository Management Scripts

A collection of Python scripts to manage your GitHub repositories - fetch commits, delete commits, update descriptions, and manage visibility settings.

## Available Scripts

### 1. `fetch_commits.py` - Fetch Commits by Date
Fetches all commits you made on a specific date across all your GitHub repositories.

**Features:**
- Searches all repositories for commits by date
- Extracts repository name, commit ID, message, and timestamp
- Outputs to JSON file for further processing
- Efficient API usage with pagination

**How it works:**
1. Authenticates with GitHub API using your personal access token
2. Fetches all your repositories (owned, collaborated, organization)
3. For each repository, searches for commits by author and date
4. Aggregates all commits into a single JSON file

### 2. `undo_commits.py` - Delete Commits Safely
Deletes commits from GitHub repositories with human-in-the-loop confirmation and safety checks.

**Features:**
- Interactive confirmation for each repository
- Beautiful CLI with tables and button selection
- Safety checks to prevent deleting newer commits
- Detailed preview showing commit details and files changed
- Skip & retry functionality with separate output file
- Progress tracking and final summary

**How it works:**
1. Loads commits from `commits.json` or `skipped_commits.json`
2. For each repository, displays commit details and GitHub URL
3. Performs safety check to ensure no commits exist after deletion targets
4. Asks for user confirmation via interactive buttons (Yes/No/Skip)
5. If confirmed: clones repo, resets HEAD to before commits, force pushes
6. Saves results to `deleted_commits.json` and `skipped_commits.json`

**Safety Features:**
- Automatically skips repositories with commits after deletion targets
- Uses `git reset --hard` for atomic deletion of multiple commits
- Shows detailed warnings before force push operations
- Cannot delete commits if newer work exists

### 3. `update_descriptions.py` - Manage Repository Descriptions
Bulk update or clear descriptions for all your repositories.

**Features:**
- Fetches all repositories you own
- Interactive mode with multiple options
- Beautiful table display with current descriptions
- Bulk operations or selective updates
- Export current descriptions to JSON

**How it works:**
1. Fetches all repositories via GitHub API
2. Displays repositories in a formatted table
3. Presents options: clear all, set all to custom, select specific, export
4. Updates repository descriptions via GitHub API PATCH requests
5. Saves results with before/after descriptions

**Operations:**
- Clear all descriptions (set to empty)
- Set all to same custom description
- Export current descriptions to backup file
- Track updated/skipped/failed repositories

### 4. `update_visibility.py` - Manage Repository Visibility
Make repositories private or public with human-in-the-loop confirmation.

**Features:**
- Review each repository individually or bulk update all
- Shows repository stats (stars, forks, last updated)
- Interactive button selection with arrow keys
- Safety warnings when making repositories public
- Export current visibility status

**How it works:**
1. Fetches all repositories you own via GitHub API
2. Displays current visibility status (private/public) in a table
3. Presents options: all private, all public, individual review, export
4. For individual review: shows each repo with current visibility
5. Updates visibility via GitHub API PATCH requests
6. Saves results to `visibility_updates.json`

**Safety Features:**
- Skips repositories already in desired state
- Shows warning panel before making repos public
- Requires explicit confirmation for bulk operations
- Tracks all changes for audit trail

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Create GitHub Personal Access Token

1. Go to [GitHub Token Settings](https://github.com/settings/tokens)
2. Click "Generate new token" (classic)
3. Give it a descriptive name (e.g., "Commit Fetcher")
4. Select scopes:
   - `repo` (for access to private repositories)
   - OR `public_repo` (if you only need public repositories)
5. Click "Generate token" and copy it

### 3. Set Environment Variable

**Linux/macOS:**
```bash
export GITHUB_TOKEN='your_token_here'
```

**Windows (Command Prompt):**
```cmd
set GITHUB_TOKEN=your_token_here
```

**Windows (PowerShell):**
```powershell
$env:GITHUB_TOKEN='your_token_here'
```

Or create a `.env` file (copy from `.env.example`):
```bash
cp .env.example .env
# Edit .env and add your token
```

Then load it before running the script:
```bash
export $(cat .env | xargs)
```

## Usage

### Fetch Commits

Fetch all commits from a specific date:

```bash
# Basic usage
python fetch_commits.py 2025-11-26

# Custom output file
python fetch_commits.py 2025-11-26 --output my_commits.json

# Fetch today's commits
python fetch_commits.py $(date +%Y-%m-%d)
```

### Delete Commits

Delete commits with interactive confirmation:

```bash
# Interactive mode (default)
python undo_commits.py

# Use custom input file (retry skipped commits)
python undo_commits.py --input skipped_commits.json

# Custom output file
python undo_commits.py --output my_results.json

# Plain text mode (no colors)
python undo_commits.py --no-rich
```

See [README_UNDO.md](README_UNDO.md) for detailed documentation.

### Update Descriptions

Manage repository descriptions:

```bash
# Interactive mode
python update_descriptions.py

# Clear all descriptions
python update_descriptions.py --clear

# Set all to custom description
python update_descriptions.py --set "My custom description"

# Export current descriptions
python update_descriptions.py --export

# Plain text mode
python update_descriptions.py --no-rich
```

### Update Visibility

Make repositories private or public:

```bash
# Interactive mode (review each repo)
python update_visibility.py

# Make all repositories private
python update_visibility.py --all-private

# Make all repositories public (with warning)
python update_visibility.py --all-public

# Export current visibility status
python update_visibility.py --export

# Plain text mode
python update_visibility.py --no-rich
```

## Output Files

### `commits.json`
Generated by `fetch_commits.py`:
```json
{
  "date": "2025-11-26",
  "total_commits": 5,
  "commits": [
    {
      "repository": "username/repo-name",
      "commit_id": "abc123def456...",
      "commit_message": "Fix bug in authentication",
      "timestamp": "2025-11-26T10:30:45Z",
      "url": "https://github.com/username/repo-name/commit/abc123"
    }
  ]
}
```

### `deleted_commits.json`
Generated by `undo_commits.py`:
```json
{
  "execution_date": "2025-11-26T18:30:00.000000",
  "statistics": {
    "total_repos": 10,
    "processed_repos": 8,
    "deleted_commits": 125,
    "skipped_commits": 4
  },
  "results": [...]
}
```

### `skipped_commits.json`
Generated by `undo_commits.py` (can be used as input for retry):
```json
{
  "date": "2025-11-26T18:30:00.000000",
  "commits": [
    {
      "repository": "owner/repo",
      "commit_sha": "abc123...",
      "commit_message": "Update README.md",
      "reason": "User declined deletion"
    }
  ]
}
```

### `description_updates.json`
Generated by `update_descriptions.py`:
```json
{
  "execution_date": "2025-11-26T18:30:00.000000",
  "statistics": {
    "total_repos": 50,
    "updated": 45,
    "skipped": 5,
    "errors": 0
  },
  "updated_repos": [...]
}
```

### `visibility_updates.json`
Generated by `update_visibility.py`:
```json
{
  "execution_date": "2025-11-26T18:30:00.000000",
  "statistics": {
    "total_repos": 50,
    "updated_to_private": 30,
    "updated_to_public": 5,
    "skipped": 15
  },
  "updated_repos": [...]
}
```

## Common Workflows

### Workflow 1: Fetch and Delete Commits
```bash
# 1. Fetch commits from a specific date
python fetch_commits.py 2025-11-26

# 2. Review and delete commits interactively
python undo_commits.py

# 3. Retry skipped commits later
python undo_commits.py --input skipped_commits.json
```

### Workflow 2: Make All Repos Private
```bash
# 1. Export current visibility status (backup)
python update_visibility.py --export

# 2. Make all repositories private
python update_visibility.py --all-private
```

### Workflow 3: Clean Up Repository Descriptions
```bash
# 1. Export current descriptions (backup)
python update_descriptions.py --export

# 2. Clear all descriptions
python update_descriptions.py --clear

# OR set all to same description
python update_descriptions.py --set "Updated description"
```

## Troubleshooting

### Error: GITHUB_TOKEN environment variable not set
Make sure you've exported the token:
```bash
export GITHUB_TOKEN='your_token_here'
```

### GitHub API Error: 401
Your token is invalid or expired. Generate a new one.

### Rate Limiting
GitHub API rate limits: 5,000 requests/hour for authenticated requests. If you hit the limit, wait an hour.

### Interactive buttons not working
Install dependencies:
```bash
pip install -r requirements.txt
```

Or use plain text mode:
```bash
python <script>.py --no-rich
```

### Permission denied when updating repos
Make sure your GitHub token has `repo` scope with write access.

### Safety check failed (undo_commits.py)
This means there are commits AFTER the ones you want to delete. Deleting would erase newer work. The repository is automatically skipped for safety.

## Important Warnings

### undo_commits.py
- Uses FORCE PUSH and permanently rewrites git history
- Cannot be undone once force pushed
- Always review commits before deletion
- Make backups if unsure

### update_visibility.py
- Making repositories public exposes all code to everyone
- Cannot easily undo for originally private repositories
- Use with caution in production environments

## Notes

- All scripts use GitHub REST API v3
- Requires Python 3.7+
- Git must be installed for `undo_commits.py`
- Progress feedback shown during execution
- All operations logged to JSON files
- Interactive mode uses beautiful CLI with `rich` and `questionary`
- Plain text mode available for CI/CD environments
