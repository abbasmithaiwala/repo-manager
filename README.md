# GitHub Commit Fetcher

A Python script to fetch all commits you made on a specific date across all your GitHub repositories.

## Features

- Fetches commits from all repositories (owned, collaborated, or organization)
- Extracts repository name, commit ID, commit message, and timestamp
- Outputs data to a JSON file
- Efficient API usage with pagination
- Progress feedback during execution

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

### Basic Usage

```bash
python fetch_commits.py 2024-11-26
```

This will:
- Search all your repositories for commits on 2024-11-26
- Save results to `commits.json`

### Custom Output File

```bash
python fetch_commits.py 2024-11-26 --output my_commits.json
```

### Help

```bash
python fetch_commits.py --help
```

## Output Format

The script generates a JSON file with the following structure:

```json
{
  "date": "2025-11-26",
  "total_commits": 5,
  "commits": [
    {
      "repository": "username/repo-name",
      "commit_id": "abc123def456...",
      "commit_message": "Fix bug in authentication",
      "timestamp": "2024-11-26T10:30:45Z",
      "url": "https://github.com/username/repo-name/commit/abc123"
    }
  ]
}
```

## Fields Explained

- **repository**: Full repository name (owner/repo)
- **commit_id**: Full SHA hash of the commit
- **commit_message**: Complete commit message
- **timestamp**: ISO 8601 formatted timestamp
- **url**: Direct link to the commit on GitHub

## Examples

### Fetch commits from a specific date
```bash
python fetch_commits.py 2025-11-26
```

### Fetch today's commits
```bash
python fetch_commits.py $(date +%Y-%m-%d)
```

### Fetch yesterday's commits
```bash
python fetch_commits.py $(date -d "yesterday" +%Y-%m-%d)
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
The script respects GitHub's rate limits (5,000 requests/hour for authenticated requests). If you hit the limit, wait an hour or use a different token.

## Notes

- The script searches commits using GitHub's API filter by author and date range
- Empty repositories are skipped automatically
- Progress is shown for each repository being checked
- The script includes both console output and JSON file output
