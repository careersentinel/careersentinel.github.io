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

`scripts/berlin_jobs.py` does the site part. The week file is
`internal/berlin-jobs/<Monday>.json` (git-ignored, so the spares and notes
never go public):

```json
{
  "week": "2026-11-02",
  "english_ads": 450,
  "german_required": 138,
  "jobs":   [{"company": "Doctolib", "role": "Senior Software Engineer, Node.js/TypeScript", "url": "https://..."}],
  "spares": [{"company": "Vercel", "role": "...", "url": "https://...", "greenhouse_board": "optional"}]
}
```

`jobs` holds 12, `spares` a few more. `english_ads` is the English Berlin ads
long enough to check, `german_required` how many of those still ask for German.
The page only ever says "about N in 10".

1. `python3 scripts/berlin_jobs.py check <week file>` asks each job board
   whether each job is still open, swaps a closed one for the next open spare
   in the same spot, writes the file back, and exits 1 if fewer than 12 are open.
   A 200 from the ad page is not enough (Ashby answers 200 for closed jobs).
2. `python3 scripts/berlin_jobs.py build <week file>` writes
   `berlin-english-jobs/<week>/index.html` from `scripts/berlin_jobs_week.html`,
   moves the "latest" pointer, and ages old weeks: banner at 21 days,
   `noindex` at 56. Old pages get nothing else.
3. Commit and push to `main`; Vercel deploys it.
4. The LinkedIn post is built from the same week file, so the page and the post
   always name the same 12 jobs. Run `check` again right before posting; if it
   swaps a job, rebuild and push before the post goes out.

To change the page copy, edit `scripts/berlin_jobs_week.html`, run
`founder-voice` and the `copy-checker` agent, then rebuild the current week.

## Analytics

Page views come from Vercel Web Analytics like the rest of the site. Each card
also sends a cookieless `job_click` event (and `cta_click` for the waitlist and
CV check). Vercel only records custom events on paid plans; on Hobby they are
dropped and the page works the same. Waitlist sign-ups from this page carry the
`utm_campaign` in their source, like the Instagram links.
