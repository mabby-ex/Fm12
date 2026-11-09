"""Score Football Manager 2012 players and staff from FM12's Print Screen exports, and write the pages.

    python3 score.py                  score the active save (config.toml) -> out/<save>/*.html
    python3 score.py --open [PAGE]    ...then open a page in the browser (default: last)
    python3 score.py --save NAME      score another save
    python3 score.py init             first-time setup: config.toml and a save
    python3 score.py exports          list the newest Print Screen files in config.toml's exports_dir
    python3 score.py import [FILE...] --date YYYY-MM-DD --source my-club
                                      read Print Screen files (default: the newest) into the save, then score it

Reads saves/<save>/obs/<YYYY-MM-DD>_<source>_<view>.csv (players) and saves/<save>/staff/<YYYY-MM-DD>_<source>.csv,
scores them with weights/<save.toml's weights>.toml, and writes one page per entry in PAGES.
"""
import argparse
import csv
import html
import json
import re
import sys
import time
import tomllib
import webbrowser
from pathlib import Path

import fm12export

ROOT = Path(__file__).parent
CONFIG = ROOT / "config.toml"
PAGES = ["squad", "grid", "elsewhere", "last", "filters", "charts", "staff", "last_staff", "staff_filters", "settings"]  # keys 1-9 then 0, in this order
META = {"Name", "Club", "Age", "Left Foot", "Wage", "Transfer Value", "Loan", "Minutes", "Rating", "Division"}  # every other column is an attribute
STAFF_META = {"Name", "Club", "Age", "Job", "Personality"}
LEFT_FOOTED = {"Fairly Strong", "Strong", "Very Strong"}
PARTIAL_SQUAD = re.compile(r"-(u\d+s?|reserves)$")  # source of a youth/reserve squad screen: not the whole club
SEARCH_MIN_WEIGHT = 2  # attributes weighted below this are left out of the filters page's search minimums
GRID_PCT_AGE = 24  # the grid page shows vs Age next to the score for senior players this age and under



def load_toml(path):
    return tomllib.loads(path.read_text(encoding="utf-8"))


def money(text):
    """'£1.5K p/w' -> 1500.0, '£15,000 p/w' -> 15000.0, '€2.1M' -> 2100000.0; None for N/A or blank. Any currency
    symbol. Wages per year or month ('£780K p/a', '£65K p/m') become per week."""
    text = text.strip().replace(",", "")
    m = re.match(r"\D*?([\d.]+)\s*([KMB]?)", text, re.I)
    if not m:
        return None
    v = float(m.group(1)) * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[m.group(2).upper()]
    per = re.search(r"p\s*/\s*([wma])\b", text, re.I)
    return v / {"w": 1, "m": 52 / 12, "a": 52}[per.group(1).lower()] if per else v


def weighted(attrs, groups):
    """Each group's Σ(attribute × weight) / Σ(weights), for the groups whose attributes are all known."""
    return {key: sum(attrs[a] * x for a, x in w.items()) / sum(w.values())
            for key, w in groups.items() if all(a in attrs for a in w)}


def timeline(dates):
    """(date, snapshot, attributes known by then), oldest first: each attribute carries forward until re-observed."""
    attrs = {}
    for date in sorted(dates):
        attrs.update(dates[date]["attrs"])
        yield date, dates[date], dict(attrs)


def read_rows(folder):
    """(path, row) for every CSV row in a folder, oldest file first."""
    for path in sorted(folder.glob("*.csv")) if folder.exists() else []:
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                yield path, row


# --- players ---

def num(v):
    """An attribute from a CSV cell: 14, or 13.5 (the middle of a scouting range)."""
    f = float(v)
    return int(f) if f.is_integer() else f


def load_players(obs_dir, aliases=None):
    """Every observation row, grouped by player name (truncated names via `aliases` to the full one) and then game date;
    plus each file's date, source and clubs."""
    players, files = {}, {}
    for path, row in read_rows(obs_dir):
        row["Name"] = (aliases or {}).get(row["Name"], row["Name"])
        date, source, view = path.stem[:10], path.stem[11:].rsplit("_", 1)[0], path.stem.rsplit("_", 1)[1]
        files.setdefault(path.name, {"date": date, "source": source, "clubs": set()})["clubs"].add(row["Club"])
        p = players.setdefault(row["Name"], {"keeper": False, "files": set(), "dates": {}})
        p["keeper"] |= view == "gk"  # anyone in a GK view is a keeper
        p["files"].add(path.name)
        snap = p["dates"].setdefault(date, {"attrs": {}})
        snap.update(club=row["Club"], age=int(row["Age"]))
        if row.get("Left Foot"):
            snap["leftFoot"] = row["Left Foot"]
        if row.get("Wage"):
            snap["wage"] = money(row["Wage"])
        if row.get("Transfer Value"):
            lo, _, hi = row["Transfer Value"].partition(" - ")
            snap["value"] = (money(lo), money(hi or lo))
        if "Loan" in row:  # squad screens only: "in" (blue name), "out" (red name), "trial" (yellow name) or blank
            snap["loan"] = row["Loan"] or None
        if row.get("Rating"):  # season minutes and average rating, from search screens that show them
            snap.update(minutes=int(float(row["Minutes"])) if row.get("Minutes") else None,
                        rating=float(row["Rating"]), division=row.get("Division") or None)
        snap["attrs"].update({k: num(v) for k, v in row.items() if k not in META and v})  # blank = not shown
    return players, files


def player_row(name, p, w):
    """A player's latest state, plus their history: one entry per observation date."""
    positions = {"GK": w["gk"]} if p["keeper"] else w["outfield"]
    ages = sorted(int(a) for a in w["age_benchmark"])
    known = {"leftFoot": None, "wage": None, "value": (None, None), "loan": None}
    history = []
    for date, snap, attrs in timeline(p["dates"]):
        known.update({k: v for k, v in snap.items() if k in known})
        scores = weighted(attrs, positions)
        if not scores:
            missing = sorted({a for pw in positions.values() for a in pw} - set(attrs))
            raise SystemExit(f"{name}: not enough attributes to score any position on {date}. "
                             f"Add these columns to the FM view: {', '.join(missing)}")
        best = max(scores, key=scores.get)
        bench = w["age_benchmark"][str(min(max(snap["age"], ages[0]), ages[-1]))]
        history.append({"date": date, "club": snap["club"], "age": snap["age"], "leftFoot": known["leftFoot"],
                        **scores, "best": best, "score": scores[best], "vsAge": scores[best] / bench,
                        "minutes": snap.get("minutes"), "rating": snap.get("rating"), "division": snap.get("division"),
                        "attrs": attrs})
    latest = history[-1]
    return {
        "name": name,
        **{k: v for k, v in latest.items() if k not in ("date", "leftFoot", "attrs")},  # rating: latest observation only
        "left": None if known["leftFoot"] is None else "yes" if known["leftFoot"] in LEFT_FOOTED else "no",
        "loan": known["loan"], "wage": known["wage"], "valueLo": known["value"][0], "value": known["value"][1],  # value sorts on the top of FM's range
        "history": history,
    }


def player_cols(w, with_club):
    wage = {"key": "wage", "label": "Wage", "num": True, "fmt": "money"}
    club = [{"key": "club", "label": "Club"}, wage, {"key": "value", "label": "Value", "num": True, "fmt": "range"}]
    return [
        {"key": "name", "label": "Player"},
        *(club if with_club else []),
        {"key": "age", "label": "Age", "num": True},
        *([] if with_club else [wage]),
        {"key": "left", "label": "Left", "fmt": "yesno"},
        *({"key": p, "label": p, "num": True, "fmt": "f1"} for p in ["GK", *w["outfield"]]),
        {"key": "best", "label": "Best"},
        {"key": "score", "label": "Score", "num": True, "fmt": "f1"},
        {"key": "vsAge", "label": "vs Age", "num": True, "fmt": "pct"},
        *([{"key": "rating", "label": "Rating", "num": True, "fmt": "f2"},
           {"key": "minutes", "label": "Mins", "num": True}] if with_club else []),
    ]


def filters(squad, w):
    """Per position: the squad's best (top 3 outfield, top 1 GK) and suggested FM search minimums."""
    out = []
    for pos, pw in {"GK": w["gk"], **w["outfield"]}.items():
        ranked = sorted((r for r in squad if r.get(pos) is not None), key=lambda r: -r[pos])[:1 if pos == "GK" else 3]
        if not ranked:
            continue
        rows = []
        for attr, weight in sorted(pw.items(), key=lambda kv: -kv[1]):
            values = [r["history"][-1]["attrs"][attr] for r in ranked]
            rows.append({"attr": attr, "weight": weight, "values": values,
                         "min": int(sum(values) / len(values) + 0.5) if weight >= SEARCH_MIN_WEIGHT else None})
        out.append({"pos": pos, "rows": rows,
                    "players": [{"name": r["name"], "age": r["age"], "score": r[pos]} for r in ranked]})
    return out


def charts(rows, squad, w, cfg):
    """Players rated in their latest observation (a league search, one per division), plus the squad."""
    out = []
    for r, mine in [*((r, False) for r in rows if r["rating"] is not None and r not in squad), *((r, True) for r in squad)]:
        attrs = r["history"][-1]["attrs"]
        out.append({"name": r["name"], "club": r["club"], "division": r["division"], "age": r["age"], "squad": mine, "wage": r["wage"],
                    "rating": r["rating"], "minutes": r["minutes"], "best": r["best"],
                    "scores": {p: r[p] for p in ["GK", *w["outfield"]] if r.get(p) is not None},
                    "Acceleration": attrs.get("Acceleration"), "Pace": attrs.get("Pace"), "Jumping": attrs.get("Jumping"), "Agility": attrs.get("Agility")})
    return {"positions": [*w["outfield"], "GK"], "players": out,
            "managed": cfg["managed_club"], "division": cfg.get("division")}


def grid(squad, w, cfg, intake):
    """The squad by formation slot (save.toml's `grid`): senior players by position score, then youth
    (age <= youth_age) by that position's score against their age benchmark. Players are placed best first, each at
    their best position: its first free Starter, else Backup, else Third, which takes any number (players to sell or
    loan out), shared across that position's slots. A left-footer prefers a left-footed slot. Out on loan isn't placed.
    save.toml's `grid_pins` (name = slot label, or { slot = label, col = "starter" | "backup" | "third" }, either
    part optional, plus row = n for the nth slot with that label; pinning places a player out on loan too) puts a
    player in that slot instead, whatever their foot; other players steer clear of slots a pinned player is still to
    fill. Players pinned to a column go first, into that column.
    The latest youth intake (`intake`: names) gets its own columns, placed like the youth, except those in `grid_youth`."""
    slots = cfg.get("grid") or [{"label": p, "pos": p} for p in ["GK", *w["outfield"]]]
    columns = ["starter", "backup", "third"]
    pins = {n: v if isinstance(v, dict) else {"slot": v} for n, v in cfg.get("grid_pins", {}).items()}
    pin_col = {n: columns.index(v["col"]) for n, v in pins.items() if v.get("col") in columns}
    pinned_any = set(pins)  # pinned to a slot, a column, or both (a column alone: their best position)
    pin_row = {n: v["row"] for n, v in pins.items() if v.get("slot") and v.get("row")}
    pins = {n: v["slot"] for n, v in pins.items() if v.get("slot")}
    check_listed({"grid_pins": list(pins)}, "grid_pins", {r["name"] for r in squad}, "names players not in the squad")
    if bad := set(pins.values()) - {s["label"] for s in slots}:
        raise SystemExit(f"save.toml grid_pins names slots not in grid: {sorted(bad)}")
    pin_fits = {}  # name -> the slots they're pinned to (every slot with that label, or just its `row`th)
    for n, label in pins.items():
        fits = [i for i, s in enumerate(slots) if s["label"] == label]
        if n in pin_row:
            if not 1 <= pin_row[n] <= len(fits):
                raise SystemExit(f"save.toml grid_pins: {n}'s row {pin_row[n]}, but grid has {len(fits)} {label!r} slot(s)")
            fits = [fits[pin_row[n] - 1]]
        pin_fits[n] = fits
    youth_age = cfg.get("youth_age", 18)
    promoted = set(cfg.get("grid_senior", []))  # youngsters the user has moved up to the senior squad
    check_listed(cfg, "grid_senior", {r["name"] for r in squad}, "names players not in the squad")
    joined = set(cfg.get("grid_youth", []))  # intake players the user has kept: youth columns, not intake
    check_listed(cfg, "grid_youth", {r["name"] for r in squad}, "names players not in the squad")
    intake = intake - joined
    excluded = set(cfg.get("grid_exclude", []))  # still at the club but not in the plans (e.g. contract running out)
    check_listed(cfg, "grid_exclude", {r["name"] for r in squad}, "names players not in the squad")
    squad = [r for r in squad if r["name"] not in excluded]
    here = [r for r in squad if r["loan"] != "out" or r["name"] in pinned_any]  # out on loan: only if pinned

    def allocate(players, value, pct):
        cols, spare = [[[] for _ in slots] for _ in range(3)], []  # Starter, Backup, Third: lists of players per slot
        waiting = {}  # slot -> pinned players not yet placed: others steer clear of those slots at the same depth
        for r in players:
            for i in range(len(slots)):
                waiting[i] = waiting.get(i, 0) + (i in pin_fits.get(r["name"], ()))
        for r in sorted(players, key=lambda r: (r["name"] not in pin_col, -value(r, r["best"]))):
            fits = (pin_fits[r["name"]] if r["name"] in pins else
                    [i for i, s in enumerate(slots) if r.get(s["pos"]) is not None and (not s.get("left") or r["left"] == "yes")])
            if not fits:
                spare.append(r)
                continue
            pos = max({slots[i]["pos"] for i in fits}, key=lambda pos: value(r, pos))  # best position in the formation
            ok = [i for i in fits if slots[i]["pos"] == pos]
            pinned = r["name"] in pins
            if pinned:
                for i in fits:
                    waiting[i] -= 1
            # left-footed slots first (only left-footers reach them), then slots no pinned player is waiting for
            pref = lambda i: (not slots[i].get("left"), 0 if pinned else waiting[i], i)
            depths = (pin_col[r["name"]],) if r["name"] in pin_col else (0, 1)
            free = [(d, *pref(i), i) for d in depths if d < 2 for i in ok if not cols[d][i]]
            d, i = (min(free)[0], min(free)[-1]) if free else (2, min(ok, key=lambda i: (len(cols[2][i]), *pref(i))))
            cols[d][i].append({"name": r["name"], "age": r["age"], "loan": r["loan"], "v": value(r, pos), "score": r[pos], "left": r["left"] == "yes",
                               "pct": r[pos] * r["vsAge"] / r["score"] if pct and r["age"] <= GRID_PCT_AGE else None})
        return cols, spare

    is_senior = lambda r: r["age"] > youth_age or r["name"] in promoted
    senior, spare = allocate([r for r in here if is_senior(r)], lambda r, pos: r[pos], True)
    vs_age = lambda r, pos: r[pos] * r["vsAge"] / r["score"]  # score ÷ age benchmark
    youth, spare_youth = allocate([r for r in here if not is_senior(r) and r["name"] not in intake], vs_age, False)
    new, spare_new = allocate([r for r in here if not is_senior(r) and r["name"] in intake], vs_age, False)
    brief = lambda r, v: {"name": r["name"], "age": r["age"], "pos": r["best"], "v": v}
    return {"youthAge": youth_age, "pctAge": GRID_PCT_AGE,
            "slots": [{"label": s["label"], "pos": s["pos"], "left": bool(s.get("left")),
                       "senior": [c[i] for c in senior], "youth": [c[i] for c in youth],
                       "intake": [c[i] for c in new]} for i, s in enumerate(slots)],
            "spare": [brief(r, r["score"]) for r in sorted(spare, key=lambda r: -r["score"])],
            "spareYouth": [brief(r, r["vsAge"]) for r in sorted(spare_youth + spare_new, key=lambda r: -r["vsAge"])],
            "loanOut": [brief(r, r["score"]) for r in squad if r["loan"] == "out" and r["name"] not in pinned_any],
            "players": {r["name"]: r for r in squad}}  # for the history overlay


# --- staff ---

def load_staff(staff_dir, words):
    """Every staff observation row, grouped by name and then game date. FM12 shows numbers; any words (later FMs)
    become numbers via the weights file's [staff_words]."""
    staff = {}
    for path, row in read_rows(staff_dir):
        p = staff.setdefault(row["Name"], {"files": set(), "dates": {}})
        p["files"].add(path.name)
        snap = p["dates"].setdefault(path.stem[:10], {"attrs": {}})
        snap.update(club=row["Club"], age=int(row["Age"]) if row.get("Age") else None,
                    job=row.get("Job") or None, personality=row.get("Personality") or None)
        for k, v in row.items():
            if k not in STAFF_META and v:  # blank = not shown
                if re.fullmatch(r"\d+(\.\d+)?", v):
                    snap["attrs"][k] = num(v)
                    continue
                if v not in words:
                    raise SystemExit(f"{path.name}: {row['Name']}: {k} = {v!r} isn't in the weights file's [staff_words]")
                snap["attrs"][k] = words[v]
    return staff


def staff_row(name, p, roles):
    """A staff member's latest state and role scores, plus their history by observation date."""
    history, known = [], {"job": None, "personality": None}
    for date, snap, attrs in timeline(p["dates"]):
        known.update({k: snap[k] for k in known if snap[k]})
        scores = weighted(attrs, roles)
        best = max(scores, key=scores.get, default=None)
        history.append({"date": date, "club": snap["club"], "age": snap["age"], **scores,
                        "best": best, "score": scores.get(best), "attrs": attrs})
    latest = history[-1]
    return {"name": name, **{k: v for k, v in latest.items() if k not in ("date", "attrs")}, **known, "history": history}


def staff_cols(roles):
    return [{"key": "name", "label": "Name"}, {"key": "club", "label": "Club"}, {"key": "age", "label": "Age", "num": True},
            {"key": "job", "label": "Job"}, {"key": "personality", "label": "Personality"},
            *({"key": r, "label": r, "num": True, "fmt": "f1"} for r in roles)]


def staff_filters(club_staff, roles, words, names):
    """Per role: the club's best staff at it (top 3) and suggested minimums for FM's staff search, as FM's words."""
    def word(v):  # the word whose value is nearest; FM12 searches by number, so with no words it's the number
        return min(words, key=lambda w: abs(words[w] - v)) if words else int(v + 0.5)
    out = []
    for role, rw in roles.items():
        ranked = sorted((r for r in club_staff if r.get(role) is not None), key=lambda r: -r[role])[:3]
        if not ranked:
            continue
        rows = []
        for attr, weight in sorted(rw.items(), key=lambda kv: -kv[1]):
            values = [r["history"][-1]["attrs"][attr] for r in ranked]
            rows.append({"attr": attr, "weight": weight, "values": values, "labels": [word(v) for v in values],
                         "min": word(sum(values) / len(values)) if weight >= SEARCH_MIN_WEIGHT else None})
        out.append({"pos": role, "title": names.get(role) if names.get(role) != role else None, "rows": rows,
                    "players": [{"name": r["name"], "age": r["age"], "score": r[role]} for r in ranked]})
    return out


# --- pages ---

def check_listed(cfg, key, known, what):
    if missing := set(cfg.get(key, [])) - known:
        raise SystemExit(f"save.toml {key} {what}: {sorted(missing)}")


def settings(config, save):
    """The settings page: each settings file and what's in it."""
    return [{"path": path, "values": load_toml(ROOT / path)} for path in ("config.toml", f"saves/{save}/save.toml")]


def build(save, config):
    """Every page's (columns, data)."""
    save_dir = ROOT / "saves" / save
    if not (save_dir / "save.toml").exists():
        raise SystemExit(f"No saves/{save}/save.toml: run `python3 score.py init` to set up a save")
    cfg = load_toml(save_dir / "save.toml")
    w = load_toml(ROOT / "weights" / f"{cfg['weights']}.toml")
    managed = cfg["managed_club"]

    players, obs_files = load_players(save_dir / "obs", cfg.get("aliases"))
    rows = [player_row(n, p, w) for n, p in players.items()]
    check_listed(cfg, "last_names", players.keys(), "has players never observed")
    check_listed(cfg, "last_batch", set(obs_files), "names files with no players")
    last_batch, last_names = set(cfg.get("last_batch", [])), set(cfg.get("last_names", []))

    # Anyone at the managed club but missing from its latest squad screen has left (sold, released).
    # A youth or reserve squad screen (`my-club-u18s`) shows only part of the club, so it doesn't count.
    squad_date = max((f["date"] for f in obs_files.values() if not f["source"].startswith("search-")
                      and not PARTIAL_SQUAD.search(f["source"]) and managed in f["clubs"]), default="")
    # ...as has anyone in save.toml's `released` (sold or released since the latest squad screen)
    check_listed(cfg, "released", players.keys(), "has players never observed")
    for r in rows:
        if r["club"] == managed and (r["history"][-1]["date"] < squad_date or r["name"] in cfg.get("released", [])):
            r["club"] = f"left {managed}"
    # ...and anyone in `signed` (signed since the latest squad screen) has joined, until a newer squad screen leaves them out
    check_listed(cfg, "signed", players.keys(), "has players never observed")
    for r in rows:
        if r["name"] in cfg.get("signed", []) and r["history"][-1]["date"] >= squad_date:
            r["club"] = managed
    # ...and anyone in `recalled` is back from loan (clears the "out" flag until the next squad screen)
    check_listed(cfg, "recalled", players.keys(), "has players never observed")
    for r in rows:
        if r["name"] in cfg.get("recalled", []) and r["loan"] == "out":
            r["loan"] = None
    # ...and save.toml's `loan` (FM12's text exports don't show the coloured names): "Name" = "in" | "out" | "trial"
    check_listed({"loan": list(cfg.get("loan", {}))}, "loan", players.keys(), "has players never observed")
    for r in rows:
        if r["name"] in cfg.get("loan", {}):
            r["loan"] = cfg["loan"][r["name"]] or None
    squad = [r for r in rows if r["club"] == managed]
    # The latest youth intake: players in the newest obs file(s) whose source mentions "intake", until a squad screen
    # shows them (signed: they join the youth; let go: they've left)
    intake_date = max((f["date"] for f in obs_files.values() if "intake" in f["source"]), default="")
    intake = {n for n, p in players.items()
              if any(obs_files[f]["date"] == intake_date and "intake" in obs_files[f]["source"] for f in p["files"])
              and not any(obs_files[f]["date"] >= intake_date and not obs_files[f]["source"].startswith("search-") for f in p["files"])}

    roles = w.get("staff", {})
    staff = load_staff(save_dir / "staff", w.get("staff_words", {}))
    staff_rows = [staff_row(n, p, roles) for n, p in staff.items()]
    check_listed(cfg, "last_staff_batch", {f for p in staff.values() for f in p["files"]}, "names files with no staff")
    check_listed(cfg, "last_staff_names", staff.keys(), "has staff never observed")
    last_staff, last_staff_names = set(cfg.get("last_staff_batch", [])), set(cfg.get("last_staff_names", []))
    # The club's staff: as for players, anyone at the managed club but missing from its latest staff screen has left
    club_dates = [f[:10] for p in staff.values() for f in p["files"]
                  if not f[11:].startswith("search-") and p["dates"][f[:10]]["club"] == managed]
    club_staff = [r for r in staff_rows if r["club"] == managed and r["history"][-1]["date"] >= max(club_dates, default="")]

    return cfg, {
        "squad": (player_cols(w, False), squad),
        "grid": (player_cols(w, False), grid(squad, w, cfg, intake)),  # the columns are for the history overlay
        "elsewhere": (player_cols(w, True), [r for r in rows if r["club"] != managed]),
        # a list of just names (e.g. a shortlist) picks players already observed; otherwise the batch's files
        "last": (player_cols(w, True), [r for r in rows if r["name"] in last_names] if last_names
                 else [r for r in rows if players[r["name"]]["files"] & last_batch]),
        "filters": ([], filters(squad, w)),
        "charts": ([], charts(rows, squad, w, cfg)),
        "staff": (staff_cols(roles), staff_rows),
        # the batch's files, plus anyone named in last_staff_names
        "last_staff": (staff_cols(roles), [r for r in staff_rows
                                           if staff[r["name"]]["files"] & last_staff or r["name"] in last_staff_names]),
        "staff_filters": ([], staff_filters(club_staff, roles, w.get("staff_words", {}), w.get("staff_names", {}))),
        "settings": ([], settings(config, save)),
    }


def write_pages(save, config, cfg, pages):
    out = ROOT / "out" / save
    out.mkdir(parents=True, exist_ok=True)
    home = html.escape(cfg["short_name"])
    labels = {p: home if p == "squad" else p.replace("_", " ") for p in PAGES}
    keys = {p: str(i % 10) for i, p in enumerate(PAGES, 1)}  # the tenth page is key 0
    dates = [f.name[:10] for d in ("obs", "staff") for f in (ROOT / "saves" / save / d).glob("*.csv")]
    site = json.dumps({"pages": {keys[p]: p for p in PAGES}, "currency": config.get("currency", "£"),
                       "gameDate": max(dates, default=None)})  # the latest game date: the history overlay's "years ago"
    theme = (ROOT / "theme.css").read_text(encoding="utf-8")
    w = load_toml(ROOT / "weights" / f"{cfg['weights']}.toml")
    weights = json.dumps({"GK": w["gk"], **w["outfield"], **w.get("staff", {})}, ensure_ascii=False)  # for the history overlay
    for page, (columns, data) in pages.items():
        nav = "".join(f'<a href="{p}.html"{" class=\"on\"" if p == page else ""}>{keys[p]} {labels[p]}</a>' for p in PAGES)
        data = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")  # a "</script>" in a name can't end the script
        template = (ROOT / ("charts.html" if page == "charts" else "template.html")).read_text(encoding="utf-8")
        page_html = (template.replace("__THEME__", theme).replace("__NAV__", nav)
                     .replace("__TITLE__", f"{home} · {labels[page]}").replace("__SAVE__", save)
                     .replace("__HOME__", home).replace("__PAGE__", page).replace("__SITE__", site)
                     .replace("__COLS__", json.dumps(columns)).replace("__WEIGHTS__", weights).replace("__DATA__", data))
        (out / f"{page}.html").write_text(page_html, encoding="utf-8")
    print(f"[{save}] out/{save}/: " + ", ".join(f"{p} ({len(d)})" for p, (_, d) in pages.items()
                                                 if p not in ("grid", "filters", "charts", "staff_filters", "settings")))
    return out


# --- commands ---

def load_config():
    if not CONFIG.exists():
        raise SystemExit("No config.toml yet: run `python3 score.py init` to set one up")
    return load_toml(CONFIG)


def default_exports_dir():
    """FM2012's own folder (Windows: in Documents), a sensible place to save Print Screen files."""
    return "~/Documents/Sports Interactive/Football Manager 2012"


def toml_str(s):
    return json.dumps(s, ensure_ascii=False)  # a JSON string is a valid TOML basic string


def init():
    """Ask for the settings a new user needs, and write config.toml and saves/<save>/save.toml."""
    old = load_toml(CONFIG) if CONFIG.exists() else {}

    def ask(prompt, default=""):
        answer = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
        return answer or default

    weights = sorted(p.stem for p in (ROOT / "weights").glob("*.toml"))
    print("Set up config.toml and a save. Press enter to keep the [default].\n")
    exports = ask("Folder you save FM's Print Screen files to", old.get("exports_dir", default_exports_dir()))
    currency = ask("Currency symbol FM shows", old.get("currency", "£"))
    club = ask("Club you manage, exactly as FM shows it")
    while not club:
        club = ask("Club you manage (needed)")
    save = ask("Name for this save (a folder name)", re.sub(r"[^a-z0-9]+", "-", club.lower()).strip("-"))
    division = ask("Your club's division, exactly as FM shows it (optional)")
    weight = ask(f"Weights to score with ({', '.join(weights)})", weights[-1] if weights else "")

    save_toml = ROOT / "saves" / save / "save.toml"
    if save_toml.exists():
        print(f"\nsaves/{save}/save.toml already exists: left as it is")
    else:
        (save_toml.parent / "obs").mkdir(parents=True, exist_ok=True)
        (save_toml.parent / "staff").mkdir(exist_ok=True)
        save_toml.write_text(f"# A save managing {club}. The settings page (key 0) shows them.\n"
                             f"weights = {toml_str(weight)}\nmanaged_club = {toml_str(club)}\n"
                             f"short_name = {toml_str(save)}\ndivision = {toml_str(division)}\n"
                             "last_batch = []\nlast_staff_batch = []\n", encoding="utf-8")
        print(f"\nWrote saves/{save}/save.toml")
    CONFIG.write_text("# Settings for this computer. The settings page (key 0) shows them.\n"
                      f"active_save = {toml_str(save)}\nexports_dir = {toml_str(exports)}\n"
                      f"currency = {toml_str(currency)}\n", encoding="utf-8")
    print("Wrote config.toml. Next: in FM, press Ctrl+P on your squad screen and save it as a text file,\n"
          "then run `python score.py import --date <FM's date> --source my-club`.")


def exports_folder(config):
    folder = Path(config.get("exports_dir", default_exports_dir())).expanduser()
    if not folder.is_dir():
        raise SystemExit(f"Exports folder {folder} doesn't exist: set exports_dir in config.toml")
    return folder


def recent_exports(config, minutes):
    """Print Screen files in exports_dir from the last `minutes`, newest first."""
    folder = exports_folder(config)
    files = sorted((p for p in folder.iterdir() if p.suffix.lower() in fm12export.EXPORT_TYPES),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    now = time.time()
    return [p for p in files if now - p.stat().st_mtime <= minutes * 60], files


def exports(minutes):
    """List the newest Print Screen files, so the user (or an agent) can find the ones just saved."""
    config = load_config()
    recent, files = recent_exports(config, minutes)
    now = time.time()
    for p in recent:
        print(f"{int(now - p.stat().st_mtime):>6}s ago  {p}")
    if not recent:
        newest = f"; the newest is {files[0].name}, {int((now - files[0].stat().st_mtime) / 60)} min ago" if files else ""
        print(f"No exports in {exports_folder(config)} from the last {minutes:g} min{newest}")


def set_toml_list(path, key, values, drop=()):
    """Set `key = [...]` in a save.toml, keeping everything else as it is; remove the `drop` keys."""
    text = path.read_text(encoding="utf-8")
    line = f"{key} = [{', '.join(toml_str(v) for v in values)}]"
    pattern = re.compile(rf"^{key}\s*=\s*\[[^\]]*\]", re.M)
    text = pattern.sub(lambda _: line, text) if pattern.search(text) else text.rstrip("\n") + "\n" + line + "\n"
    for k in drop:
        text = re.sub(rf"^{k}\s*=\s*\[[^\]]*\]\n?", "", text, flags=re.M)
    path.write_text(text, encoding="utf-8")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def import_exports(args):
    """Read Print Screen files into the active save's obs/ and staff/ folders, set last_batch, and score."""
    config = load_config()
    save = args.save or config["active_save"]
    save_dir = ROOT / "saves" / save
    cfg = load_toml(save_dir / "save.toml")
    files = [Path(f) for f in args.files] or recent_exports(config, args.minutes)[0]
    if not files:
        raise SystemExit(f"No Print Screen files from the last {args.minutes:g} min: name the files, or use --minutes")
    date = args.date
    while not date or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        if not sys.stdin.isatty():
            raise SystemExit("Give FM's in-game date: --date YYYY-MM-DD (FM shows it day first: 1/7/2012 = 2012-07-01)")
        date = input("FM's in-game date, as YYYY-MM-DD (FM shows 1/7/2012 for 2012-07-01): ").strip()
    dates = [f.name[:10] for d in ("obs", "staff") for f in (save_dir / d).glob("*.csv")]
    if dates and date < max(dates) and not args.force:
        raise SystemExit(f"{date} is before this save's latest data ({max(dates)}): a different save? (--force to import anyway)")
    source = args.source
    if not source:
        if not sys.stdin.isatty():
            raise SystemExit("Say what the files are: --source my-club (your squad) or --source search-<what> (a search)")
        source = input(f"What is this? your squad = {slug(cfg['managed_club'])}, a search = search-<what> (search-cb): ").strip()
    source = slug(source) if not source.startswith("search-") else "search-" + slug(source[7:])
    club = "" if source.startswith("search-") else cfg["managed_club"]  # a squad screen has no Club column
    batch, staff_batch = [], []
    for f in files:
        written, ignored = fm12export.convert(f, save_dir, date, source, club, staff=True if args.staff else None)
        for out, n in written:
            (staff_batch if out.parent.name == "staff" else batch).append(out.name)
            print(f"{f.name} -> saves/{save}/{out.parent.name}/{out.name} ({n} rows)")
        if ignored:
            print(f"  ignored columns: {', '.join(ignored)}")
    toml = save_dir / "save.toml"
    if batch:
        set_toml_list(toml, "last_batch", sorted(set(batch)), drop=["last_names"])
    if staff_batch:
        set_toml_list(toml, "last_staff_batch", sorted(set(staff_batch)), drop=["last_staff_names"])
    return save, "last_staff" if staff_batch and not batch else "last"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--save", help="score this save instead of config.toml's active_save")
    ap.add_argument("--open", nargs="?", const="last", choices=PAGES, metavar="PAGE",
                    help=f"open a page afterwards (default: last): {', '.join(PAGES)}")
    sub = ap.add_subparsers(dest="command")
    sub.add_parser("init", help="first-time setup: config.toml and a save")
    sp = sub.add_parser("exports", help="list the newest Print Screen files in exports_dir")
    sp.add_argument("--minutes", type=float, default=10, help="how far back to look (default 10)")
    ip = sub.add_parser("import", help="read Print Screen files into the save, then score it")
    ip.add_argument("files", nargs="*", help="the files (default: those saved in the last --minutes)")
    ip.add_argument("--date", help="FM's in-game date, YYYY-MM-DD")
    ip.add_argument("--source", help="my-club (your squad screen) or search-<what> (a search, a shortlist)")
    ip.add_argument("--staff", action="store_true", help="the files are staff lists (normally detected)")
    ip.add_argument("--minutes", type=float, default=10, help="with no files: how far back to look (default 10)")
    ip.add_argument("--force", action="store_true", help="import a date earlier than the save's latest")
    ip.add_argument("--no-open", action="store_true", help="don't open the page afterwards")
    args = ap.parse_args()

    if args.command == "init":
        return init()
    if args.command == "exports":
        return exports(args.minutes)
    config = load_config()
    save = args.save or config["active_save"]
    page = args.open
    if args.command == "import":
        save, last = import_exports(args)
        page = page or (None if args.no_open else last)
    cfg, pages = build(save, config)
    out = write_pages(save, config, cfg, pages)
    if page:
        webbrowser.open((out / f"{page}.html").resolve().as_uri())


if __name__ == "__main__":
    sys.exit(main())
