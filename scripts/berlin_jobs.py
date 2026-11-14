#!/usr/bin/env python3
"""Weekly "English jobs in Berlin that don't ask for German" page.

    python3 scripts/berlin_jobs.py check internal/berlin-week-2026-11-09.json
    python3 scripts/berlin_jobs.py build internal/berlin-week-2026-11-09.json
    python3 scripts/berlin_jobs.py age        # banner / noindex on old weeks only

Input is the week file the app export writes, in the shape set out in
internal/berlin-weekly-contract.md (week, counts, german_share_in_10, roles,
shortlist, caught). It stays in internal/ (git-ignored).

`check` asks each job board whether each role is still open. A 200 from the ad
page is not enough: Ashby and most career sites answer 200 for closed jobs.
It records the answer on every role as `page_check` (open, closed, unknown),
replaces a shortlisted role that isn't confirmed open with the next one that
meets the contract's shortlist rules, writes the file back (so the LinkedIn
post, built from the same file afterwards, names the same 12) and exits 1 if
it can't get 12. Run it right before the post goes out as well.

`build` writes berlin-english-jobs/<week>/index.html from
scripts/berlin_jobs_week.html, moves the "latest" pointer and ages old weeks.
`--site DIR` builds into a copy of the site instead (for previews and tests).
Standard library only.
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import html
import json
import re
import sys
import threading
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
LEVELS = [("starting", "🌱 Starting out"), ("mid", "💼 Mid-level"), ("senior", "🚀 Senior and lead")]
# Contract shortlist rules, used when a shortlisted role has closed.
BOARDS = {"ashby", "greenhouse", "lever", "smartrecruiters", "personio", "recruitee"}
LANG_IN_TITLE = re.compile(
    r"\b(german|deutsch|dach|austria|swiss|france|french|spanish|spain|italian|italy|dutch|benelux|nordic|"
    r"polish|turkish|arabic|japanese|korean|chinese|mandarin|portuguese|russian|ukrainian|speaker|native)\b", re.I)
NEIGHBOURS = {"starting": ["mid", "senior"], "mid": ["starting", "senior"], "senior": ["mid", "starting"]}


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


_cache: dict[str, object] = {}
_lock = threading.Lock()


def _cached(key: str, fetch):
    with _lock:
        if key in _cache:
            return _cache[key]
    val = fetch()
    with _lock:
        _cache[key] = val
    return val


def _gh_api(board: str, jid: str) -> str:
    s, _, b = _get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{jid}")
    if s == 200 and b.startswith("{") and json.loads(b).get("title"):
        return "open"
    return "closed" if s == 404 and "Job not found" in b else "unknown"


def job_status(role: dict) -> tuple[str, str]:
    """Return (open|closed|unknown, how we know) for one role's url."""
    url = role["url"]
    m = re.match(r"https://jobs\.ashbyhq\.com/([^/]+)/([0-9a-f-]{36})", url)
    if m:
        def board():
            s, _, b = _get(f"https://api.ashbyhq.com/posting-api/job-board/{m.group(1)}")
            return {j["id"] for j in json.loads(b).get("jobs", [])} if s == 200 else None
        ids = _cached("ashby:" + m.group(1).lower(), board)
        if ids is None:
            return "unknown", "ashby board api failed"
        return ("open", "ashby board lists it") if m.group(2) in ids else ("closed", "not on ashby board")
    m = re.match(r"https://jobs\.(eu\.)?lever\.co/([^/]+)/([0-9a-f-]{36})", url)
    if m:
        api = "api.eu.lever.co" if m.group(1) else "api.lever.co"
        s, _, _ = _get(f"https://{api}/v0/postings/{m.group(2)}/{m.group(3)}")
        return ("open" if s == 200 else "closed" if s == 404 else "unknown"), f"lever api {s}"
    m = re.match(r"https://(?:job-)?boards\.greenhouse\.io/([^/]+)/jobs/(\d+)", url)
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
        return ("closed" if s in (200, 404) else "unknown"), f"eu greenhouse page {s}"
    m = re.match(r"https://(?:jobs|careers)\.smartrecruiters\.com/([^/]+)/(\d+)", url)
    if m:
        s, _, _ = _get(f"https://api.smartrecruiters.com/v1/companies/{m.group(1)}/postings/{m.group(2)}")
        return ("open" if s == 200 else "closed" if s == 404 else "unknown"), f"smartrecruiters api {s}"
    m = re.match(r"https://([^./]+)\.jobs\.personio\.(de|com)/job/(\d+)", url)
    if m:
        def feed():
            s, _, b = _get(f"https://{m.group(1)}.jobs.personio.{m.group(2)}/xml")
            return set(re.findall(r"<id>(\d+)</id>", b)) if s == 200 else None
        ids = _cached(f"personio:{m.group(1)}", feed)
        if ids is None:
            return "unknown", "personio feed failed"
        return ("open", "personio feed lists it") if m.group(3) in ids else ("closed", "not in personio feed")
    m = re.match(r"https://([^./]+)\.recruitee\.com/o/([^/?#]+)", url)
    if m:
        def offers():
            s, _, b = _get(f"https://{m.group(1)}.recruitee.com/api/offers/")
            return {o.get("slug") for o in json.loads(b).get("offers", [])} if s == 200 else None
        slugs = _cached(f"recruitee:{m.group(1)}", offers)
        if slugs is None:
            return "unknown", "recruitee api failed"
        return ("open", "recruitee lists it") if m.group(2) in slugs else ("closed", "not on recruitee")
    g = re.search(r"[?&]gh_jid=(\d+)", url)
    if g:
        board = role.get("greenhouse_board") or _guess_board(url)
        if board:
            st = _gh_api(board, g.group(1))
            if st != "unknown":
                return st, f"greenhouse api ({board}): {st}"
    # Last resort: the ad page loads and names the role.
    s, _, b = _get(url)
    if s in (404, 410):
        return "closed", f"page {s}"
    words = [w for w in re.findall(r"[A-Za-z]{4,}", role.get("title", "")) if w.lower() not in {"senior", "junior"}]
    if s == 200 and words and all(w.lower() in b.lower() for w in words[:3]):
        return "open", "page loads and names the role"
    return "unknown", f"page {s}"


def _guess_board(url: str) -> str | None:
    host = re.sub(r"^www\.|^careers\.|^jobs\.", "", url.split("/")[2])
    return host.split(".")[0] or None


def _eligible(role: dict, used_companies: set[str]) -> bool:
    lines = " ".join(role.get("language_lines") or []).lower()
    return (role.get("source") in BOARDS
            and role.get("page_check") == "open"
            and "german" not in lines and "deutsch" not in lines
            and not LANG_IN_TITLE.search(role.get("title", ""))
            and role.get("company", "").strip().lower() not in used_companies)


def check(week_file: Path, workers: int = 8) -> int:
    data = json.loads(week_file.read_text())
    roles = data["roles"]
    short = [int(i) for i in data["shortlist"]]
    # Shortlist first, so its answers come back early; then everything else.
    order = short + [i for i in range(len(roles)) if i not in short]
    with cf.ThreadPoolExecutor(workers) as ex:
        for i, (st, why) in zip(order, ex.map(lambda i: job_status(roles[i]), order)):
            roles[i]["page_check"], roles[i]["page_check_why"] = st, why
    log, swaps, new_short = [], [], []
    used = set()
    for i in short:
        r = roles[i]
        if r["page_check"] == "open":
            new_short.append(i)
            used.add(r["company"].strip().lower())
            continue
        log.append(f"{r['page_check']:7} {r['company']}: {r['title']}  ({r['page_check_why']})")
        new_short.append(None)  # fill below, once every kept company is known
    for k, i in enumerate(new_short):
        if i is not None:
            continue
        lost = roles[short[k]]
        pick = None
        for lvl in [lost.get("level", "mid")] + NEIGHBOURS.get(lost.get("level", "mid"), []):
            pick = next((j for j, r in enumerate(roles)
                         if j not in new_short and r.get("level") == lvl and _eligible(r, used)), None)
            if pick is not None:
                break
        if pick is None:
            log.append(f"  no replacement for {lost['company']}")
            continue
        new_short[k] = pick
        used.add(roles[pick]["company"].strip().lower())
        swaps.append({"out": short[k], "in": pick})
        log.append(f"  SWAPPED {lost['company']}: {lost['title']} -> {roles[pick]['company']}: {roles[pick]['title']}")
    data["shortlist"] = [i for i in new_short if i is not None]
    data["page_checked_at"] = dt.datetime.now().astimezone().isoformat(timespec="minutes")
    data["page_check_swaps"] = data.get("page_check_swaps", []) + swaps
    week_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    counts = {s: sum(r.get("page_check") == s for r in roles) for s in ("open", "closed", "unknown")}
    print("\n".join(log) or "all 12 picks open")
    print(f"picks: {len(data['shortlist'])} of {WANT} open. all roles: {counts}")
    return 0 if len(data["shortlist"]) >= WANT else 1


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


ARROW = '<span class="go"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 17 17 7M8 7h9v9"/></svg></span>'


def _esc(role: dict) -> tuple[str, str, str]:
    return (html.escape(clean(role["company"])), html.escape(clean(role["title"])),
            html.escape(role["url"], quote=True))


def card(role: dict) -> str:
    co, title, url = _esc(role)
    return (f'      <li><a href="{url}" target="_blank" rel="noopener" data-job="{co}">'
            f'<span class="co">{co}</span><span class="role">{title}</span>{ARROW}</a></li>\n')


def row(role: dict) -> str:
    co, title, url = _esc(role)
    return (f'        <li><a href="{url}" target="_blank" rel="noopener" data-job="{co}" data-list="all">'
            f'<span class="co">{co}</span><span class="t">{title}</span></a></li>\n')


def _by_level(roles: list[dict]) -> dict[str, list[dict]]:
    out = {k: [] for k, _ in LEVELS}
    for r in roles:
        out[r.get("level") if r.get("level") in out else "mid"].append(r)
    return out


def caught_html(caught: list[dict]) -> str:
    items = []
    for c in caught[:3]:  # company and url are for checking only; never published
        line = clean(c.get("german_line", "")).strip(" .\"'“”")
        if not line or not c.get("title"):
            continue
        # The quote comes straight from the ad; skip it if it names the employer.
        if c.get("company") and clean(c["company"]).lower() in line.lower():
            continue
        items.append(f'      <li>A <b>{html.escape(clean(c["title"]))}</b> ad, all in English, asking for '
                     f'<q>{html.escape(line)}</q></li>\n')
    if not items:
        return ""
    return ('\n  <section class="caught">\n    <h2>🔍 Caught in the check</h2>\n    <ul>\n'
            + "".join(items) + "    </ul>\n  </section>\n")


def render(data: dict) -> str:
    monday = dt.date.fromisoformat(data["week"]["start"])
    assert monday.weekday() == 0, "week must start on a Monday"
    roles = data["roles"]
    short = [int(i) for i in data["shortlist"]][:WANT]
    if len(short) < WANT:
        raise SystemExit(f"only {len(short)} picks, need {WANT}")
    picks = [roles[i] for i in short]
    # Everything not known to be closed. Unchecked files list every role.
    listed = [r for r in roles if r.get("page_check") != "closed"]
    picks_html = ""
    for key, label in LEVELS:
        group = _by_level(picks)[key]
        if group:
            picks_html += (f'    <h3 class="lvl">{label}</h3>\n    <ol class="jobs">\n'
                           + "".join(card(r) for r in group) + "    </ol>\n")
    groups_html = ""
    for key, label in LEVELS:
        group = sorted(_by_level(listed)[key], key=lambda r: (clean(r["company"]).lower(), clean(r["title"]).lower()))
        if group:
            groups_html += (f'    <details>\n      <summary>{label}<span class="n">{len(group)}</span></summary>\n'
                            f'      <ul class="rows">\n' + "".join(row(r) for r in group) + "      </ul>\n    </details>\n")
    n = int(data["german_share_in_10"])
    vals = {
        "WEEK": monday.isoformat(),
        "N_ROLES": f"{len(listed):,}",
        "N_ADS": f"{int(data['counts']['english_checkable']):,}",
        "SHARE": f"{n} in 10" if n >= 1 else "fewer than 1 in 10",
        "PICKS": picks_html, "CAUGHT": caught_html(data.get("caught") or []), "GROUPS": groups_html,
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
        if age >= NOINDEX_AFTER_DAYS and "<!-- noindex: on -->" not in s:
            s = s.replace('<link rel="stylesheet" href="/fonts/fonts.css">',
                          '<meta name="robots" content="noindex">\n<!-- noindex: on -->\n<link rel="stylesheet" href="/fonts/fonts.css">', 1)
        if s != orig:
            p.write_text(s)
            done.append(w)
    return done


def build(week_file: Path) -> None:
    data = json.loads(week_file.read_text())
    week = data["week"]["start"]
    out = PAGES / week / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(data))
    point_latest(week)
    print(f"wrote berlin-english-jobs/{week}/index.html; latest -> {week}")
    for w in age_old_weeks():
        print("aged", w)


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--site" in args:
        k = args.index("--site")
        PAGES = Path(args[k + 1]) / "berlin-english-jobs"
        del args[k:k + 2]
    cmd = args[0] if args else ""
    if cmd == "check":
        sys.exit(check(Path(args[1])))
    elif cmd == "build":
        build(Path(args[1]))
    elif cmd == "render":  # print only, for tests
        sys.stdout.write(render(json.loads(Path(args[1]).read_text())))
    elif cmd == "age":
        print("\n".join(age_old_weeks()) or "nothing to age")
    else:
        raise SystemExit(__doc__)
