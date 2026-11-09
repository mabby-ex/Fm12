"""Read FM2012 "Print Screen" exports (text, RTF or web page) into the observation CSVs score.py scores.

FM2012 can print any table to a file: press Ctrl+P (or FM menu -> Print Screen) on a player or staff list and
save it as a text file or a web page. Both are tables, which this module reads without any guessing from images:

    text / RTF:   | Name           | Age | Acc | Ant | ...      (rows of cells between | bars, lines of dashes between)
    web page:     <table><tr><th>Name</th><th>Age</th>...      (an ordinary HTML table)

Column headings can be FM's abbreviations (Acc, Ant, Cmp...) or full names; both map to FM12's full attribute names.
Stdlib only.
"""
import csv
import html.parser
import re
from pathlib import Path

EXPORT_TYPES = {".txt", ".rtf", ".html", ".htm"}

# --- column names ---

# Player attributes as FM12 names them. Later FMs renamed some: those names map back too, so a weights file
# or an export from another version still lines up.
PLAYER_ATTRS = {
    # technical
    "Cor": "Corners", "Cro": "Crossing", "Dri": "Dribbling", "Fin": "Finishing", "Fir": "First Touch",
    "Fre": "Free Kick Taking", "Hea": "Heading", "Lon": "Long Shots", "L Th": "Long Throws", "LTh": "Long Throws",
    "Mar": "Marking", "Pas": "Passing", "Pen": "Penalty Taking", "Tck": "Tackling", "Tec": "Technique",
    # mental
    "Agg": "Aggression", "Ant": "Anticipation", "Bra": "Bravery", "Cmp": "Composure", "Cnt": "Concentration",
    "Dec": "Decisions", "Det": "Determination", "Fla": "Flair", "Ldr": "Influence",  # not "Inf": that's FM's info column
    "OtB": "Off The Ball", "Pos": "Positioning", "Tea": "Teamwork", "Vis": "Vision", "Wor": "Work Rate",
    # physical
    "Acc": "Acceleration", "Agi": "Agility", "Bal": "Balance", "Jum": "Jumping", "Nat": "Natural Fitness",
    "Pac": "Pace", "Sta": "Stamina", "Str": "Strength",
    # goalkeeping
    "Aer": "Aerial Ability", "Cmd": "Command of Area", "Com": "Communication", "Ecc": "Eccentricity",
    "Han": "Handling", "Kic": "Kicking", "1v1": "One on Ones", "Ref": "Reflexes", "TRO": "Rushing Out",
    "Pun": "Tendency to Punch", "Thr": "Throwing",
    # later FMs' names for the same attributes
    "Jumping Reach": "Jumping", "Aerial Reach": "Aerial Ability", "Leadership": "Influence",
    "Rushing Out (Tendency)": "Rushing Out", "Punching (Tendency)": "Tendency to Punch",
    "Command Of Area": "Command of Area", "One On Ones": "One on Ones", "Free Kicks": "Free Kick Taking",
}
# Staff attributes as FM12 names them (all 1-20 numbers in FM12).
STAFF_ATTRS = {
    # coaching
    "Att": "Attacking", "Def": "Defending", "Fit": "Fitness", "Gk": "Goalkeepers", "GK": "Goalkeepers",
    "Gkp": "Goalkeepers", "Goalkeeping": "Goalkeepers", "Men": "Mental", "Tcs": "Tactical", "Tct": "Tactical",
    "Tac": "Tactical", "Tec": "Technical", "Yth": "Working With Youngsters", "Yng": "Working With Youngsters",
    "Wwy": "Working With Youngsters", "Working with Youngsters": "Working With Youngsters",
    # mental
    "Ada": "Adaptability", "Det": "Determination", "Dis": "Level of Discipline", "Disc": "Level of Discipline",
    "Discipline": "Level of Discipline", "Man": "Man Management", "Mgm": "Man Management",
    "People Management": "Man Management", "Mot": "Motivating",
    # knowledge
    "JPA": "Judging Player Ability", "JA": "Judging Player Ability", "JCA": "Judging Player Ability",
    "JPP": "Judging Player Potential", "JP": "Judging Player Potential",
    "TCo": "Tactical Knowledge", "TK": "Tactical Knowledge", "Tac Kn": "Tactical Knowledge",
    # medical
    "Phy": "Physiotherapy", "Physio": "Physiotherapy",
}
PLAYER_FULL = set(PLAYER_ATTRS.values())
STAFF_FULL = set(STAFF_ATTRS.values())
# Headings only a staff list has (FM's Tec is Technique for players but Technical for staff, so it doesn't count)
_PLAYER_HEADINGS = {k.lower() for k in PLAYER_ATTRS} | {v.lower() for v in PLAYER_FULL}
STAFF_ONLY = {k.lower() for k, v in STAFF_ATTRS.items() if v not in PLAYER_FULL} - _PLAYER_HEADINGS
STAFF_ONLY |= {v.lower() for v in STAFF_FULL - PLAYER_FULL}

# Non-attribute columns, by the headings FM12 may give them -> the CSV column score.py reads.
META = {
    "Name": "Name", "Player": "Name", "Person": "Name", "Staff": "Name",
    "Club": "Club", "Team": "Club", "Age": "Age",
    "Left Foot": "Left Foot", "Preferred Foot": "Preferred Foot", "Foot": "Preferred Foot",
    "Wage": "Wage", "Wages": "Wage", "Value": "Transfer Value", "Transfer Value": "Transfer Value",
    "Mins": "Minutes", "Minutes": "Minutes", "Av Rat": "Rating", "Av. Rat": "Rating", "Av Rating": "Rating",
    "Average Rating": "Rating", "Rating": "Rating", "Division": "Division", "Comp": "Division",
    "Competition": "Division", "League": "Division",
    "Position": "Position", "Best Pos": "Position", "Best Position": "Position",
    "Job": "Job", "Role": "Job", "Preferred Job": "Job", "Personality": "Personality",
}
PLAYER_COLUMNS = ["Name", "Club", "Age", "Left Foot", "Wage", "Transfer Value", "Loan", "Minutes", "Rating", "Division"]
STAFF_COLUMNS = ["Name", "Club", "Age", "Job", "Personality"]
FOOT_WORDS = ["Very Weak", "Weak", "Reasonable", "Fairly Strong", "Strong", "Very Strong"]


def _key(s):
    return re.sub(r"[\s.]+", " ", s).strip().lower()


def column_map(headers, staff):
    """Each heading -> (kind, name): kind is 'meta', 'attr' or None (ignored)."""
    attrs = STAFF_ATTRS if staff else PLAYER_ATTRS
    full = STAFF_FULL if staff else PLAYER_FULL
    by_key = {_key(k): v for k, v in attrs.items()} | {_key(v): v for v in full}
    meta = {_key(k): v for k, v in META.items()}
    out = []
    for h in headers:
        k = _key(h)
        if k in meta and not (k == "pos" and not staff):
            out.append(("meta", meta[k]))
        elif k in by_key:
            out.append(("attr", by_key[k]))
        else:
            out.append((None, h))
    return out


# --- reading files ---

def read_text(path):
    """A file's text, whatever encoding FM wrote it in."""
    raw = Path(path).read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("latin-1")


def rtf_to_text(rtf):
    """Plain text from an RTF file: enough for FM's tables (lines of text in a monospaced font)."""
    text = re.sub(r"\{\\\*[^{}]*\}", "", rtf)  # ignorable destinations
    text = re.sub(r"\{\\(fonttbl|colortbl|stylesheet|info)(?:[^{}]|\{[^{}]*\})*\}", "", text)
    text = re.sub(r"\\'([0-9a-fA-F]{2})", lambda m: bytes([int(m.group(1), 16)]).decode("cp1252", "replace"), text)
    text = re.sub(r"\\u(-?\d+)\??", lambda m: chr(int(m.group(1)) % 65536), text)
    text = re.sub(r"\\(par|line|row)\b ?", "\n", text)
    text = re.sub(r"\\cell\b ?", "|", text)
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", text)
    text = text.replace("\\{", "{").replace("\\}", "}").replace("\\\\", "\\")
    return text.replace("{", "").replace("}", "")


class _Tables(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.row, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []
        elif tag == "br" and self.cell is not None:
            self.cell.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if any(self.row):
                self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def table_rows(path):
    """Every row of the table in an export, as lists of cell strings (the heading row included)."""
    text = read_text(path)
    if Path(path).suffix.lower() in (".html", ".htm") or re.search(r"<table", text, re.I):
        p = _Tables()
        p.feed(text)
        return p.rows
    if text.lstrip().startswith("{\\rtf"):
        text = rtf_to_text(text)
    rows = []
    for line in text.splitlines():
        if "|" not in line or not re.sub(r"[|\-=+\s]", "", line):
            continue  # not a table row, or a rule of dashes
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)
    return rows


def find_header(rows):
    """Index of the heading row: the first with a Name-like column."""
    names = {_key(k) for k, v in META.items() if v == "Name"}
    for i, row in enumerate(rows):
        if any(_key(c) in names for c in row):
            return i
    raise ValueError("no heading row with a Name column: is this an FM table export?")


# --- values ---

def number(v):
    """'14' -> 14, '12-15' (a scouting range) -> 13.5, '-' or '' -> None."""
    v = v.strip()
    if m := re.fullmatch(r"(\d+(?:\.\d+)?)", v):
        f = float(m.group(1))
        return int(f) if f.is_integer() else f
    if m := re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", v):
        f = (int(m.group(1)) + int(m.group(2))) / 2
        return int(f) if f.is_integer() else f
    return None


def left_foot(row):
    """'Left Foot' in words, from FM12's Left Foot column (words or a 1-20 number) or Preferred Foot."""
    v = row.get("Left Foot", "").strip()
    if v:
        for w in sorted(FOOT_WORDS, key=len, reverse=True):
            if v.lower() == w.lower():
                return w
        if (n := number(v)) is not None:  # 1-20
            return FOOT_WORDS[min(int((n - 1) / 20 * 6), 5)]
        return ""
    pref = row.get("Preferred Foot", "").strip().lower()
    return {"left": "Very Strong", "left only": "Very Strong", "either": "Strong",
            "right": "Weak", "right only": "Very Weak"}.get(pref, "")


def age(v):
    m = re.match(r"\s*(\d+)", v or "")
    return m.group(1) if m else ""


# --- tables ---

def parse(path, staff=None):
    """Read an export into (kind, rows, ignored headings): kind 'staff' or 'player'; rows are dicts of CSV columns,
    attributes as numbers (None = not shown or unscouted). `staff` forces the kind."""
    rows = table_rows(path)
    h = find_header(rows)
    headers, body = rows[h], rows[h + 1:]
    if staff is None:
        staff = any(_key(h) in STAFF_ONLY for h in headers)
    cols = column_map(headers, staff)
    if staff is False and sum(k == "attr" for k, _ in cols) < 3:
        raise ValueError(f"{Path(path).name}: fewer than 3 attribute columns recognised in {headers}")
    out = []
    for cells in body:
        if cells == headers or len(cells) < len(headers) // 2:
            continue  # a repeated heading or a stray line
        meta, attrs = {}, {}
        for (kind, name), cell in zip(cols, cells):
            if kind == "meta":
                meta[name] = cell
            elif kind == "attr":
                attrs[name] = number(cell)
        name = re.sub(r"\s+", " ", meta.get("Name", "")).strip()
        if not name:
            continue
        r = {"Name": name, "Club": meta.get("Club", "").strip(), "Age": age(meta.get("Age")),
             "Position": meta.get("Position", "").strip()}
        if staff:
            r |= {"Job": meta.get("Job", "").strip(), "Personality": meta.get("Personality", "").strip()}
        else:
            rating = meta.get("Rating", "").strip()
            r |= {"Left Foot": left_foot(meta), "Wage": meta.get("Wage", "").strip(),
                  "Transfer Value": meta.get("Transfer Value", "").strip(), "Loan": "",
                  "Minutes": str(number(meta.get("Minutes", "").replace(",", "")) or "") if rating else "",
                  "Rating": rating if number(rating) is not None else "",
                  "Division": meta.get("Division", "").strip() if number(rating) is not None else ""}
        r["attrs"] = attrs
        out.append(r)
    ignored = [n for k, n in cols if k is None and n]
    return ("staff" if staff else "player"), out, ignored


GK_ATTRS = ["Handling", "Reflexes", "One on Ones", "Aerial Ability", "Command of Area", "Kicking"]
OUTFIELD_ATTRS = ["Finishing", "Tackling", "Dribbling", "Crossing", "Marking", "Heading", "Long Shots"]


def is_keeper(r):
    """From the Position column when there is one; else whichever of the GK / outfield attributes are higher."""
    if r["Position"]:
        return bool(re.match(r"\s*GK\b", r["Position"]))
    gk = [r["attrs"][a] for a in GK_ATTRS if r["attrs"].get(a) is not None]
    of = [r["attrs"][a] for a in OUTFIELD_ATTRS if r["attrs"].get(a) is not None]
    if gk and of:
        return sum(gk) / len(gk) > sum(of) / len(of) + 3
    return bool(gk) and not of


def write_csv(path, columns, rows):
    """Write rows (dicts of CSV columns plus 'attrs'), merging into an existing file: a name already there is
    replaced by its new row. Attribute columns are the union, alphabetical."""
    old = []
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            old = list(csv.DictReader(f))
    new = {r["Name"]: {**{c: r.get(c, "") for c in columns},
                       **{a: "" if v is None else str(v) for a, v in r["attrs"].items()}} for r in rows}
    merged = [o for o in old if o["Name"] not in new] + list(new.values())
    attrs = sorted({k for r in merged for k in r if k not in columns})
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, [*columns, *attrs], extrasaction="ignore")
        w.writeheader()
        for r in merged:
            w.writerow({k: r.get(k, "") for k in [*columns, *attrs]})
    return len(new)


def convert(path, save_dir, date, source, club="", staff=None):
    """One export -> CSV file(s) under save_dir: obs/<date>_<source>_outfield.csv and/or _gk.csv for players,
    staff/<date>_<source>.csv for staff. Rows without a Club get `club`. Returns [(written path, rows)], ignored headings."""
    kind, rows, ignored = parse(path, staff)
    for r in rows:
        r["Club"] = r["Club"] or club
        if not r["Age"] and kind == "player":
            raise SystemExit(f"{Path(path).name}: {r['Name']} has no Age: add the Age column to the FM view")
    written = []
    if kind == "staff":
        out = save_dir / "staff" / f"{date}_{source}.csv"
        written.append((out, write_csv(out, STAFF_COLUMNS, rows)))
    else:
        for view, group in (("outfield", [r for r in rows if not is_keeper(r)]), ("gk", [r for r in rows if is_keeper(r)])):
            if group:
                out = save_dir / "obs" / f"{date}_{source}_{view}.csv"
                written.append((out, write_csv(out, PLAYER_COLUMNS, group)))
    return written, ignored
