# Weekly list: English jobs in Berlin that don't ask for German

One page per week, plus one fixed address that always points at the newest week.

- `berlin-english-jobs/YYYY-MM-DD/index.html` is one week. The date is the Monday
  the data week starts (2026-11-02 = jobs first seen 2 to 8 Nov). It only ever
  holds that week's jobs.
- `berlin-english-jobs/index.html` is the fixed address
  (careersentinel.de/berlin-english-jobs/). It redirects to the newest week.

Note: this file is public like everything else in this repo. Numbers and notes
behind each list stay in the private `internal/` folder.

## Every week (automated)

`scripts/berlin_jobs.py` does the site part. Its input is the week file the
app export writes, `internal/berlin-week-<Monday>.json` (git-ignored). The
shape is set out in `internal/berlin-weekly-contract.md`: `week`, `counts`,
`german_share_in_10`, `roles` (every English Berlin role that week with no
German requirement found, each with a `level` of starting, mid or senior),
`shortlist` (12 indexes into `roles`) and `caught` (up to 3 ads that did ask
for German; company and URL are for checking only and never shown).

The page shows the 12 picks grouped by level (🌱 Starting out, 💼 Mid-level,
🚀 Senior and lead, the same labels as the post), then the caught ads by role
title and German line only, then every role in three collapsible groups. The
numbers are always "about N in 10", never the raw German count.

1. `python3 scripts/berlin_jobs.py check <week file>` asks each job board
   whether each role is still open (a 200 from the ad page is not enough;
   Ashby answers 200 for closed jobs), marks every role `page_check`, replaces
   a pick that isn't confirmed open with the next open role that meets the
   contract's shortlist rules (same level first, one per company), writes the
   file back, and exits 1 if fewer than 12 picks are left. Run it before the
   LinkedIn prep reads the file, so the post and the page name the same 12.
2. `python3 scripts/berlin_jobs.py build <week file>` writes
   `berlin-english-jobs/<week>/index.html` from `scripts/berlin_jobs_week.html`,
   moves the "latest" pointer, and ages old weeks: banner at 21 days, `noindex`
   at 56. Old pages get nothing else. `--site DIR` builds into a copy instead.
3. Commit on a branch. Pushing to `main` (live on Vercel) waits for Maher.

To change the page copy, edit `scripts/berlin_jobs_week.html`, run
`founder-voice` and the `copy-checker` agent, then rebuild the current week.

## Analytics

Page views come from Vercel Web Analytics like the rest of the site. Each card
also sends a cookieless `job_click` event (and `cta_click` for the waitlist and
CV check). Vercel only records custom events on paid plans; on Hobby they are
dropped and the page works the same. Waitlist sign-ups from this page carry the
`utm_campaign` in their source, like the Instagram links.
