# Weekly list: English jobs in Berlin that don't ask for German

One page per week, plus one fixed address that always points at the newest week.

- `berlin-english-jobs/YYYY-MM-DD/index.html` is one week. The date is the Monday
  the data week starts (2026-11-02 = jobs first seen 2 to 8 Nov). It only ever
  holds that week's jobs.
- `berlin-english-jobs/index.html` is the fixed address
  (careersentinel.de/berlin-english-jobs/). It redirects to the newest week.

Note: this file is public like everything else in this repo. Numbers and notes
behind each list stay in the private `internal/` folder.

## Every week (about 15 minutes)

1. **Pick the jobs.** Use that week's notes in `internal/english-jobs-berlin-<date>.md`
   (12 roles plus 2 spares). Only company, role and link go on the page.
2. **Check every link on the day.** A 200 is not enough. Ashby:
   `api.ashbyhq.com/posting-api/job-board/<org>` must list the job id.
   Greenhouse: `boards-api.greenhouse.io/v1/boards/<board>/jobs/<id>` returns
   the title (EU boards: the job page must not redirect to `?error=true`).
   Lever: `api.eu.lever.co/v0/postings/<org>/<id>` returns 200. Swap in a spare
   for any dead one, and tell the LinkedIn post if it names the roles.
3. **Copy last week's folder** to the new date. In the copy, change:
   the title, description, og tags and canonical (dates and URL), the eyebrow
   date, the 450 / "about 3 in 10" numbers in the intro, the 12 cards, the
   `utm_campaign` on the waitlist button, the `week` in the click script, and
   the month in the commented-out old-week banner ("early November").
   Run `founder-voice` and the `copy-checker` agent on the changed text.
4. **Move the latest pointer.** In `berlin-english-jobs/index.html`, change the
   date in the four places marked `LATEST`.
5. **Old weeks.** On the week that is now about 3 weeks old, uncomment the
   `OLD WEEK BANNER` block (it links to the latest address, so it never needs
   another edit). Later,
   uncomment the `noindex` line in its head, or delete the folder.
6. Preview, commit, push to `main` (Vercel deploys it). The LinkedIn first
   comment gets the dated URL, so the post keeps pointing at its own 12 jobs.

## Analytics

Page views come from Vercel Web Analytics like the rest of the site. Each card
also sends a cookieless `job_click` event (and `cta_click` for the waitlist and
CV check). Vercel only records custom events on paid plans; on Hobby they are
dropped and the page works the same. Waitlist sign-ups from this page carry the
`utm_campaign` in their source, like the Instagram links.
