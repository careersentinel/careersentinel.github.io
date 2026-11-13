#!/usr/bin/env python3
"""Weekly "English jobs in Berlin that don't ask for German" page.

    python3 scripts/berlin_jobs.py check internal/berlin-jobs/2026-11-16.json
    python3 scripts/berlin_jobs.py build internal/berlin-jobs/2026-11-16.json
    python3 scripts/berlin_jobs.py age            # banners/noindex on old weeks only

The week file lives in internal/ (git-ignored): the week's Monday, the two
numbers, 12 jobs and some spares. Format: see berlin-english-jobs/README.md.

`check` asks each job board whether the job is still open (a 200 from the ad
page is not enough: Ashby and most career sites answer 200 for closed jobs),
swaps a closed or unverifiable job for the next open spare, writes the result
back to the week file and exits 1 if fewer than 12 open jobs are left.
`build` writes berlin-english-jobs/<week>/index.html from the template,
moves the "latest" pointer to it, and ages old weeks. Standard library only.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "berlin-english-jobs"
TEMPLATE = ROOT / "scripts" / "berlin_jobs_week.html"
WANT = 12
BANNER_AFTER_DAYS = 21   # "about 3 weeks"
NOINDEX_AFTER_DAYS = 56
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 Safari/605.1.15"
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


# ---------------------------------------------------------------- link check

def _get(url: str, timeout: int = 30) -> tuple[int, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.geturl(), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, url, ""
    except Exception as e:  # DNS, timeout, TLS
        return 0, url, f"{type(e).__name__}: {e}"


def _gh_api(board: str, jid: str) -> str:
    s, _, b = _get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{jid}")
    if s == 200 and b.startswith("{") and json.loads(b).get("title"):
        return "open"
    return "closed" if s == 404 and "Job not found" in b else "unknown"


def job_status(job: dict) -> tuple[str, str]:
    """Return (open|closed|unknown, how we know)."""
    url = job["url"]
    m = re.match(r"https://jobs\.ashbyhq\.com/([^/]+)/([0-9a-f-]{36})", url)
    if m:
        s, _, b = _get(f"https://api.ashbyhq.com/posting-api/job-board/{m.group(1)}")
        if s != 200:
            return "unknown", f"ashby board api {s}"
        ids = {j["id"] for j in json.loads(b).get("jobs", [])}
        return ("open", "ashby board lists it") if m.group(2) in ids else ("closed", "not on ashby board")
    m = re.match(r"https://jobs\.(eu\.)?lever\.co/([^/]+)/([0-9a-f-]{36})", url)
    if m:
        api = "api.eu.lever.co" if m.group(1) else "api.lever.co"
        s, _, _ = _get(f"https://{api}/v0/postings/{m.group(2)}/{m.group(3)}")
        return ("open", "lever api 200") if s == 200 else ("closed" if s == 404 else "unknown", f"lever api {s}")
    m = re.match(r"https://job-boards\.greenhouse\.io/([^/]+)/jobs/(\d+)", url)
    if m:
        st = _gh_api(m.group(1), m.group(2))
        return st, f"greenhouse api: {st}"
    m = re.match(r"https://job-boards\.eu\.greenhouse\.io/([^/]+)/jobs/(\d+)", url)
    if m:
        # The EU boards have no public job API; a closed job redirects to the
        # board with ?error=true.
        s, final, b = _get(url)
        if s == 200 and "error=true" not in final and "Job Application for" in b:
            return "open", "eu greenhouse page"
        return ("closed" if s in (200, 404) else "unknown"), f"eu greenhouse page {s} {final}"
    m = re.search(r"[?&]gh_jid=(\d+)", url)
    if m:
        board = job.get("greenhouse_board") or _guess_board(url)
        if board:
            st = _gh_api(board, m.group(1))
            if st != "unknown":
                return st, f"greenhouse api ({board}): {st}"
    # Last resort: the ad page loads and names the role.
    s, final, b = _get(url)
    words = [w for w in re.findall(r"[A-Za-z]{4,}", job["role"]) if w.lower() not in {"senior", "junior"}]
    if s == 200 and words and all(w.lower() in b.lower() for w in words[:3]):
        return "open", "page loads and names the role"
    return "unknown", f"page {s}, role words not found" if s == 200 else f"page {s}"


def _guess_board(url: str) -> str | None:
    host = re.sub(r"^www\.|^careers\.|^jobs\.", "", url.split("/")[2])
    return host.split(".")[0] or None


def check(week_file: Path) -> int:
    data = json.loads(week_file.read_text())
    keep, log = [], []
    spares = list(data.get("spares", []))
    for job in data["jobs"]:
        st, why = job_status(job)
        log.append(f"{st:7} {job['company']}: {job['role']}  ({why})")
        if st == "open":
            keep.append(job)
            continue
        while spares:
            sp = spares.pop(0)
            sst, swhy = job_status(sp)
            log.append(f"  spare {sst:7} {sp['company']}: {sp['role']}  ({swhy})")
            if sst == "open":
                keep.append(sp)
                log.append(f"  SWAPPED {job['company']} -> {sp['company']}")
                break
    data["jobs"], data["spares"] = keep, spares
    data["checked_at"] = dt.datetime.now().astimezone().isoformat(timespec="minutes")
    week_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print("\n".join(log))
    print(f"{len(keep)} of {WANT} open.")
    return 0 if len(keep) >= WANT else 1


# ---------------------------------------------------------------- page build

def ranges(monday: dt.date) -> dict:
    sun = monday + dt.timedelta(days=6)
    same = monday.month == sun.month
    a_long = f"{monday.day}" if same else f"{monday.day} {MONTHS[monday.month - 1]}"
    a_short = f"{monday.day}" if same else f"{monday.day} {MONTHS[monday.month - 1][:3]}"
    if monday.year != sun.year:  # 28 December 2026 to 3 January 2027
        a_long, a_short = f"{a_long} {monday.year}", f"{a_short} {monday.year}"
    end_long, end_short = f"{sun.day} {MONTHS[sun.month - 1]}", f"{sun.day} {MONTHS[sun.month - 1][:3]}"
    part = "early" if monday.day <= 10 else "mid" if monday.day <= 20 else "late"
    return {
        "RANGE_LONG": f"{a_long} to {end_long} {sun.year}",
        "RANGE_NO_YEAR": f"{a_long} to {end_long}",
        "RANGE_SHORT": f"{a_short} to {end_short} {sun.year}",
        "RANGE_BETWEEN": f"{a_long} and {end_long}",
        "BANNER_WHEN": f"{part} {MONTHS[monday.month - 1]}",
    }


def clean(text: str) -> str:
    """Job titles arrive with dashes and gender tags; the site has neither."""
    text = re.sub(r"\s*\((?:[mwfdxa]\s*/\s*){1,3}[mwfdxa]\)|\s*\((?:all genders|f/m/x|x/f/m)\)", "", text, flags=re.I)
    text = re.sub(r"\s+[–—-]\s+", ", ", text).replace("–", " to ").replace("—", ", ")
    return re.sub(r"\s{2,}", " ", text).strip(" ,")


def share_phrase(german: int, total: int) -> str:
    n = round(10 * german / total)
    return f"{n} in 10" if n >= 1 else "fewer than 1 in 10"


ARROW = '<span class="go"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 17 17 7M8 7h9v9"/></svg></span>'


def card(job: dict) -> str:
    co, role = html.escape(clean(job["company"])), html.escape(clean(job["role"]))
    url = html.escape(job["url"], quote=True)
    return (f'    <li><a href="{url}" target="_blank" rel="noopener" data-job="{co}">'
            f'<span class="co">{co}</span><span class="role">{role}</span>{ARROW}</a></li>\n')


def render(data: dict) -> str:
    monday = dt.date.fromisoformat(data["week"])
    assert monday.weekday() == 0, "week must be a Monday"
    jobs = data["jobs"][:WANT]
    if len(jobs) < WANT:
        raise SystemExit(f"only {len(jobs)} jobs, need {WANT}")
    vals = {
        "WEEK": data["week"], "COUNT": str(len(jobs)),
        "N_ADS": f"{data['english_ads']:,}",
        "SHARE": share_phrase(data["german_required"], data["english_ads"]),
        "CARDS": "".join(card(j) for j in jobs),
        **ranges(monday),
    }
    t = TEMPLATE.read_text().split("\n", 1)[1]  # drop the template note
    out = re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: vals[m.group(1)], t)
    for bad in ("—", "–", "{{"):
        assert bad not in out, f"{bad!r} in rendered page"
    return out


def point_latest(week: str) -> None:
    p = PAGES / "index.html"
    s = p.read_text()
    s2 = re.sub(r"(/berlin-english-jobs/)\d{4}-\d{2}-\d{2}(/)", rf"\g<1>{week}\g<2>", s)
    assert s2.count(f"/berlin-english-jobs/{week}/") == 4, "expected 4 LATEST spots"
    p.write_text(s2)


def age_old_weeks(today: dt.date | None = None) -> list[str]:
    today = today or dt.date.today()
    weeks = sorted(d.name for d in PAGES.iterdir() if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d.name))
    done = []
    for w in weeks[:-1]:  # never the newest
        age = (today - dt.date.fromisoformat(w)).days
        p = PAGES / w / "index.html"
        s = orig = p.read_text()
        if age >= BANNER_AFTER_DAYS:
            s = re.sub(r"<!-- OLD WEEK BANNER: [^\n]*\n(\s*<a class=\"old\"[^\n]*</a>)\n\s*-->",
                       r"<!-- OLD WEEK BANNER: on -->\n\1", s)
        if age >= NOINDEX_AFTER_DAYS and '<meta name="robots" content="noindex">\n<!-- noindex: on -->' not in s:
            s = s.replace('<link rel="stylesheet" href="/fonts/fonts.css">',
                          '<meta name="robots" content="noindex">\n<!-- noindex: on -->\n<link rel="stylesheet" href="/fonts/fonts.css">', 1)
        if s != orig:
            p.write_text(s)
            done.append(f"{w}: {'banner' if age >= BANNER_AFTER_DAYS else ''}{' + noindex' if age >= NOINDEX_AFTER_DAYS else ''}")
    return done


def build(week_file: Path) -> None:
    data = json.loads(week_file.read_text())
    out = PAGES / data["week"] / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(data))
    point_latest(data["week"])
    print(f"wrote berlin-english-jobs/{data['week']}/index.html; latest -> {data['week']}")
    for line in age_old_weeks():
        print("aged", line)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "check":
        sys.exit(check(Path(sys.argv[2])))
    elif cmd == "build":
        build(Path(sys.argv[2]))
    elif cmd == "render":  # print only, for tests
        sys.stdout.write(render(json.loads(Path(sys.argv[2]).read_text())))
    elif cmd == "age":
        print("\n".join(age_old_weeks()) or "nothing to age")
    else:
        raise SystemExit(__doc__)
