#!/bin/bash
# Weekly Berlin English jobs: export, check, build, publish the page, post.
# Hands-off by Maher's choice (13 and 14 Nov 2026). Every step must pass or
# the run stops with HOLD and the reason; nothing after a failed step runs.
#
#   scripts/berlin_weekly_run.sh            # last complete week (Mon to Sun)
#   scripts/berlin_weekly_run.sh 2026-11-09 # a given Monday
#   DRY_RUN=1 scripts/berlin_weekly_run.sh  # no push, no post (see below)
#
# Runs from a dedicated worktree on origin/main (or BUILD_REF), so it never
# switches branches in the shared checkout. The week file stays in the shared
# checkout's internal/ (git-ignored).
#
# DRY_RUN=1: export (only if the week file is missing), check, build, voice
# lint, then `cs-linkedin weekly berlin <file> --publish --dry-run` (the real
# hands-off checks, writes nothing). Nothing is pushed or posted. Before the page builder is on main, add BUILD_REF=berlin-jobs-automation.
# Overrides: EXPORT_SCRIPT (default: the app's tools/weekly_english_jobs.py),
# LINKEDIN_BIN, POST_AT (default 08:30). Exit 0 = done, 1 = HOLD (reason printed).
set -euo pipefail

BIZ="$HOME/career_sentinel_business"
APP="$HOME/career_sentinel_app"
WT="$BIZ/.claude/worktrees/weekly-publish"
POST_AT="${POST_AT:-08:30}"
BUILD_REF="${BUILD_REF:-origin/main}"
EXPORT_SCRIPT="${EXPORT_SCRIPT:-$APP/tools/weekly_english_jobs.py}"
LINKEDIN_BIN="${LINKEDIN_BIN:-$HOME/career_sentinel_linkedin/.venv/bin/cs-linkedin}"

hold() { echo "HOLD: $*"; exit 1; }
step() { echo; echo "== $*"; }

if [ $# -ge 1 ]; then WEEK="$1"; else
  WEEK=$(python3 -c 'import datetime as d; t=d.date.today(); print(t - d.timedelta(days=t.weekday() + 7))')
fi
FILE="$BIZ/internal/berlin-week-$WEEK.json"
URL="https://careersentinel.de/berlin-english-jobs/$WEEK/"
echo "week $WEEK, file $FILE, dry run: ${DRY_RUN:-0}"

step "1. export (read-only production pull)"
if [ -f "$FILE" ]; then echo "week file exists, not pulling again"; else
  # Maher's standing OK for this one weekly read (14 Nov 2026). Delete the
  # file to withdraw it; the run then stops here.
  [ -f "$BIZ/internal/berlin-weekly-standing-ok.md" ] \
    || hold "no standing OK for the weekly production read (internal/berlin-weekly-standing-ok.md)"
  python3 "$EXPORT_SCRIPT" --via-railway --week "$WEEK" \
    --out "$BIZ/internal/berlin-week-{week}.json" || hold "export failed"
fi
[ -f "$FILE" ] || hold "export wrote no file"
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert {"week","counts","german_share_in_10","roles","shortlist"} <= d.keys()' "$FILE" \
  || hold "week file is not in the contract format (is the new export on the app's main?)"

step "2. publish worktree on $BUILD_REF"
[ "$BUILD_REF" = origin/main ] || [ "${DRY_RUN:-0}" = 1 ] || hold "BUILD_REF other than origin/main is for dry runs only"
git -C "$BIZ" fetch -q origin main || hold "git fetch failed"
if [ ! -d "$WT" ]; then git -C "$BIZ" worktree add -q --detach "$WT" "$BUILD_REF" || hold "worktree add failed"; fi
git -C "$WT" checkout -q --detach "$BUILD_REF"
git -C "$WT" reset -q --hard "$BUILD_REF"
[ -f "$WT/scripts/berlin_jobs.py" ] || hold "scripts/berlin_jobs.py is not on $BUILD_REF yet"

step "3. check every link (writes the file back)"
python3 "$WT/scripts/berlin_jobs.py" check "$FILE" || hold "fewer than 12 picks are open"

step "4. build the page"
python3 "$WT/scripts/berlin_jobs.py" build "$FILE" || hold "build failed"

step "5. voice lint on the visible text"
TXT=$(mktemp -t berlin-week)
python3 - "$WT/berlin-english-jobs/$WEEK/index.html" "$TXT" <<'EOF' || hold "could not extract page text"
import html, re, sys
s = open(sys.argv[1]).read()
s = re.sub(r"<style>.*?</style>|<script>.*?</script>|<!--.*?-->", "", s, flags=re.S)
lines = [html.unescape(l.strip()) for l in re.sub(r"<[^>]+>", "\n", s).splitlines() if l.strip()]
open(sys.argv[2], "w").write("\n".join(lines) + "\n")
EOF
python3 "$HOME/.claude/skills/founder-voice/voice_lint.py" "$TXT" || hold "voice lint failed on the page text"

if [ "${DRY_RUN:-0}" = 1 ]; then
  step "dry run: LinkedIn hands-off checks, nothing written or posted"
  if [ -x "$LINKEDIN_BIN" ] && "$LINKEDIN_BIN" weekly berlin --help >/dev/null 2>&1; then
    "$LINKEDIN_BIN" weekly berlin "$FILE" --publish --dry-run || echo "(LinkedIn dry run exited $?; expected while the page isn't live)"
  else
    echo "LinkedIn command not built yet, skipped"
  fi
  echo; echo "DRY RUN done. Page built in $WT, nothing pushed or posted."; exit 0
fi

step "6. commit and push to main (Vercel deploys)"
git -C "$WT" add berlin-english-jobs
if git -C "$WT" diff --cached --quiet; then echo "page unchanged, nothing to push"; else
  git -C "$WT" -c user.name="Career Sentinel" commit -q -m "Berlin jobs: week of $WEEK (weekly run)"
  git -C "$WT" push -q origin HEAD:main || hold "push to main failed"
fi

step "7. wait until the page is live with the same 12 links"
python3 - "$FILE" "$URL" <<'EOF' || hold "page not live with the 12 picks after 10 minutes"
import html, json, sys, time, urllib.request
d = json.load(open(sys.argv[1])); url = sys.argv[2]
picks = [html.escape(d["roles"][int(i)]["url"], quote=True) for i in d["shortlist"][:12]]
for _ in range(60):
    try:
        b = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read().decode()
        if all(p in b for p in picks):
            print("live:", url); sys.exit(0)
    except Exception:
        pass
    time.sleep(10)
sys.exit(1)
EOF

step "8. LinkedIn post"
{ [ -x "$LINKEDIN_BIN" ] && "$LINKEDIN_BIN" weekly berlin --help >/dev/null 2>&1; } \
  || hold "page is live at $URL, but the LinkedIn command isn't set up yet, so nothing was posted"
NOW=$(date +%H:%M)
if [[ "$NOW" < "$POST_AT" ]]; then
  echo "waiting until $POST_AT"
  while [[ "$(date +%H:%M)" < "$POST_AT" ]]; do sleep 30; done
fi
"$LINKEDIN_BIN" weekly berlin "$FILE" --publish || hold "LinkedIn command exited $? (its output is above); page is live at $URL"

echo; echo "DONE: page $URL live, post published."
