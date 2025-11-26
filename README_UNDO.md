# GitHub Commit Deleter 🗑️

Safely delete commits from GitHub repositories with human-in-loop confirmation and beautiful CLI interface.

## Features

- ✅ **Interactive Confirmation** - Review each repository before deletion
- 🎨 **Beautiful CLI** - Rich formatting with colors, tables, and panels
- 🔘 **Button Selection** - Navigate options with arrow keys (no typing!)
- 🔒 **Safety Checks** - Prevents accidental deletion of newer commits
- 📊 **Detailed Preview** - See commit details, files changed, and more
- 💾 **Skip & Retry** - Skip commits and process them later
- 🔗 **Repository URLs** - Direct links to GitHub repos in preview
- 📈 **Progress Tracking** - Real-time status and final summary

## Installation

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Set your GitHub token:

```bash
export GITHUB_TOKEN='your_github_personal_access_token_here'
```

## Usage

### Basic Usage

Delete commits from the default file (`commits.json`):

```bash
python undo_commits.py
```

### Custom Input File

Delete commits from a custom file (e.g., skipped commits):

```bash
python undo_commits.py --input skipped_commits.json
```

### Custom Output File

Specify a custom output file for results:

```bash
python undo_commits.py --output my_results.json
```

### Plain Text Mode

Disable rich formatting (useful for CI/CD or logging):

```bash
python undo_commits.py --no-rich
```

### Help

View all options:

```bash
python undo_commits.py --help
```

## How It Works

### 1. Load Commits

The script reads commits from a JSON file with this structure:

```json
{
  "commits": [
    {
      "repository": "username/repo-name",
      "commit_id": "abc123...",
      "commit_message": "Update README.md",
      "timestamp": "2025-11-26T00:33:00Z"
    }
  ]
}
```

### 2. Preview & Confirm

For each repository, the script:

1. **Shows repository details** including GitHub URL
2. **Performs safety check** to ensure no commits will be lost
3. **Displays commit table** with SHA, message, author, files
4. **Shows file details** for each commit
5. **Asks for confirmation** via interactive buttons:
   - ✅ **Yes** - Delete these commits
   - ❌ **No** - Skip and mark for later
   - ⏭️ **Skip** - Skip this repository

### 3. Delete Commits

If you confirm:

1. Clones the repository locally
2. Resets HEAD to before the commits
3. Force pushes to GitHub
4. Shows success confirmation

### 4. Save Results

Generates two files:

- **`deleted_commits.json`** - Full results with statistics
- **`skipped_commits.json`** - Commits you skipped (ready for retry)

## Safety Features

### Automatic Safety Checks

Before deleting, the script verifies:

- ✅ No commits exist AFTER the ones being deleted
- ✅ All commits are on the current branch
- ✅ Commits are at HEAD (most recent)

### Safe Scenarios

- Commits are the most recent on the branch
- No work will be lost
- All commits can be safely deleted

### Unsafe Scenarios

The script will **automatically skip** repositories where:

- ❌ There are commits AFTER the ones to delete
- ❌ Deletion would affect other commits
- ❌ Commits are on different branches

## Example Output

```
╭──────── Repository ─────────╮
│ username/repo-name          │
│ https://github.com/user/... │
╰─────────────────────────────╯

Found 2 commit(s) to delete

🔍 Performing safety check...
✅ Safety check passed: Safe: Commits to delete are at HEAD

┌───────────────── Commits to Delete ──────────────────┐
│ #  │ SHA              │ Message          │ Author   │
├────┼──────────────────┼──────────────────┼──────────┤
│ 1  │ abc12345...      │ Update README    │ Abbas    │
│ 2  │ def67890...      │ Fix typo         │ Abbas    │
└────┴──────────────────┴──────────────────┴──────────┘

╔═══════════════════════════════════════════╗
║ ⚠️  WARNING: This will PERMANENTLY        ║
║     DELETE these 2 commit(s)              ║
║ ⚠️  This uses FORCE PUSH                  ║
║ ✅ SAFE: No other commits affected        ║
╚═══════════════════════════════════════════╝

? What would you like to do with username/repo-name?
  ✅ Yes - Delete these commits
> ❌ No - Skip and mark for later
  ⏭️  Skip this repository
```

## Workflow Examples

### Scenario 1: Delete All Commits

```bash
# 1. Run the script
python undo_commits.py

# 2. For each repo, press ↑/↓ to select "Yes"
# 3. Press Enter to confirm

# 4. Results saved to deleted_commits.json
```

### Scenario 2: Skip & Retry Later

```bash
# 1. First run - skip some repos
python undo_commits.py
# Select "No" for repos you want to review later

# 2. Check skipped commits
cat skipped_commits.json

# 3. Retry skipped commits
python undo_commits.py --input skipped_commits.json
```

### Scenario 3: Automated/CI Mode

```bash
# Use plain text mode for scripts
python undo_commits.py --no-rich > deletion_log.txt 2>&1
```

## File Formats

### Input File (`commits.json`)

Generated by `fetch_commits.py`:

```json
{
  "date": "2025-11-26",
  "total_commits": 129,
  "commits": [
    {
      "repository": "owner/repo",
      "commit_id": "full-sha-hash",
      "commit_message": "Commit message",
      "timestamp": "2025-11-26T00:33:00Z",
      "url": "https://github.com/..."
    }
  ]
}
```

### Output File (`deleted_commits.json`)

```json
{
  "execution_date": "2025-11-26T...",
  "statistics": {
    "total_repos": 10,
    "processed_repos": 8,
    "skipped_repos": 2,
    "total_commits": 129,
    "deleted_commits": 125,
    "skipped_commits": 4
  },
  "results": [
    {
      "repository": "owner/repo",
      "total_commits": 2,
      "deleted_commits": 2,
      "status": "success",
      "commit_details": [...]
    }
  ],
  "skipped_for_later": [...]
}
```

### Skipped File (`skipped_commits.json`)

```json
{
  "date": "2025-11-26T...",
  "commits": [
    {
      "repository": "owner/repo",
      "commit_sha": "abc123...",
      "commit_message": "Update README",
      "reason": "User declined deletion"
    }
  ]
}
```

## Requirements

- Python 3.7+
- Git installed and in PATH
- GitHub Personal Access Token with `repo` permissions
- Dependencies from `requirements.txt`:
  - `requests` - GitHub API calls
  - `rich` - Beautiful terminal formatting
  - `questionary` - Interactive prompts

## Troubleshooting

### "GITHUB_TOKEN not set"

```bash
export GITHUB_TOKEN='your_token_here'
```

### "git is not installed"

Install git: https://git-scm.com/downloads

### "Safety check failed"

This means there are commits AFTER the ones you want to delete. Deleting would erase newer work. The repository is automatically skipped for safety.

### "Permission denied"

Make sure your GitHub token has write access to the repositories.

### Interactive buttons not working

Install dependencies:

```bash
pip install -r requirements.txt
```

Or use plain text mode:

```bash
python undo_commits.py --no-rich
```

## Tips

1. **Always review the preview** before confirming deletion
2. **Use skip & retry** for repos you're unsure about
3. **Check safety messages** - the script protects you from accidents
4. **Save skipped commits** for later review and processing
5. **Use custom output files** to organize results by date or batch

## License

MIT License - Feel free to use and modify!

## Warning

⚠️ **This tool uses FORCE PUSH and permanently rewrites git history!**

- Always review commits before deletion
- Make backups if unsure
- Cannot be undone once force pushed
- Use in production with extreme caution

The safety checks protect you, but **you are responsible** for what you delete!
