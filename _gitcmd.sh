#!/usr/bin/env bash
# _gitcmd.sh — Run any git command against D:\Documents-CV using WSL native git-dir
# Usage from PowerShell:
#   wsl bash _gitcmd.sh status --short
#   wsl bash _gitcmd.sh add job_search/scorer.py job_search/web.py
#   wsl bash _gitcmd.sh commit -m "message"
#   wsl bash _gitcmd.sh push https://github.com/sahilrajpurkar03/Documents-CV.git main
#   wsl bash _gitcmd.sh log --oneline -5

GIT_NATIVE="/home/tedgm1d/docscv_git2"

if [ ! -d "$GIT_NATIVE" ]; then
  echo "[error] Git dir not found at $GIT_NATIVE. Run: wsl bash _fix_git.sh"
  exit 1
fi

git --git-dir="$GIT_NATIVE" --work-tree=/mnt/d/Documents-CV "$@"
