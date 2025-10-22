# Claude Code Conversation History Backup

This directory contains a backup of your Claude Code conversation history and settings.

## What's Included

- `history.jsonl` - All conversation history
- `file-history/` - File edit history
- `projects/` - Project-specific conversations
- `settings.json` - Your Claude Code settings
- `.credentials.json` - Login credentials (encrypted)
- `todos/` - Todo lists from conversations

## How to Restore

After reinstalling Pi OS and installing Claude Code:

```bash
# Navigate to your cloned repo
cd navair-add-monitor

# Restore Claude Code data
cp -r claude_backup ~/.claude

# Set proper permissions
chmod 700 ~/.claude
chmod 600 ~/.claude/.credentials.json
chmod 600 ~/.claude/history.jsonl
chmod -R 700 ~/.claude/file-history
chmod -R 700 ~/.claude/projects
chmod -R 700 ~/.claude/todos
```

## Backup Date

Created: October 22, 2025

## Note

Your conversation history will be fully restored, including all file edits, settings, and project contexts.
