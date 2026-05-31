#!/usr/bin/env bash
# _fix_git.sh — Restores git access for D:\Documents-CV via WSL native git-dir
# Run this if `wsl git -C /mnt/d/Documents-CV` stops working.
#
# After running, use git with:
#   wsl bash _gitcmd.sh add file1 file2
#   wsl bash _gitcmd.sh commit -m "message"
#   wsl bash _gitcmd.sh push https://github.com/sahilrajpurkar03/Documents-CV.git main
#   wsl bash _gitcmd.sh status --short
#   wsl bash _gitcmd.sh log --oneline -5

GIT_NATIVE="/home/tedgm1d/docscv_git2"
rm -rf "$GIT_NATIVE"
mkdir -p "$GIT_NATIVE"

# Pull latest .git from a fresh clone
TMPCLONE=$(mktemp -d)
git clone https://github.com/sahilrajpurkar03/Documents-CV.git "$TMPCLONE"
rsync -a "$TMPCLONE/.git/" "$GIT_NATIVE/"
rm -rf "$TMPCLONE"

git --git-dir="$GIT_NATIVE" --work-tree=/mnt/d/Documents-CV config core.fileMode false
echo "Git restored. Last 3 commits:"
git --git-dir="$GIT_NATIVE" --work-tree=/mnt/d/Documents-CV log --oneline -3
