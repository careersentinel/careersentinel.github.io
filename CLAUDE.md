# Career Sentinel: marketing site

The public site at careersentinel.de, served from GitHub Pages. **Not the
product.** The beta app is `~/career_sentinel_app` and has its own `CLAUDE.md`;
anything about scanning, scoring, users or the pipeline belongs there.

## What lives here

- The landing page, privacy policy and Impressum.
- `internal/agb-review-notes.md` — the four questions to take to the IHK about
  the AGB. The AGB itself is deployed in the app repo at `/terms` and `/agb`,
  live before legal review.
- `BUSINESS.md`, `DECISIONS.md`, `HANDOVER.md` — strategy and the record of
  what was decided and why.

## Writing for this site

Everything here is public-facing, so the style rules in `~/.claude/CLAUDE.md`
apply to all of it: no em-dashes, casual over polished, first name only, no
origin or permit details. The Impressum is the legal exception and carries the
full name and address.

## Legal state, as of 25 October 2026

The AGB is live and has not been reviewed by a lawyer. Four clauses are
flagged in `internal/agb-review-notes.md`, the liability clause in § 12 being
the one real problem. None of the commercial obligations bite while the beta
is free; all of them bite the day it is not. Before charging anything, read
the "Before you ever charge money" section of that file: the Button-Lösung
(§ 312j BGB), the Kündigungsbutton (§ 312k), the Widerruf waiver and the
Kleinunternehmer decision.

Open and cheap: the controller contact is still a gmail address on a site that
owns its own domain, the privacy policy has a date but no version number, and
it promises a retention period it does not state.
