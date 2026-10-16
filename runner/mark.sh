#!/bin/bash
# usage: mark.sh <iid> <msg>; appends to results/progress/<iid>.txt and pushes (best-effort)
mkdir -p results/progress; echo "$(date -u +%H:%M:%S) $2" >> results/progress/$1.txt
git config user.name swe-runner; git config user.email swe@example.invalid
git add results/progress; git commit -qm "progress $1: $2" || exit 0
for i in 1 2 3 4; do git pull -q --rebase origin "$GITHUB_REF_NAME" && git push -q origin HEAD:"$GITHUB_REF_NAME" && exit 0; sleep $((RANDOM%5+1)); done
