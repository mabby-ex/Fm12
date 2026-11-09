# FM2012 player scoring

Scores Football Manager **2012** players and staff on weighted attributes and tracks them over game time.
An FM2012 port of jamiebolden/fm-scoring (made for FM27). FM2012 can print any table to a file (Print Screen,
Ctrl+P: text, RTF or web page), and `score.py import` reads those files straight into CSV (`fm12export.py`):
no screenshots, no transcription. `score.py` turns the CSVs into ten pages per save (keys 1–9, then 0):

1. **squad**: the club the user manages
2. **grid**: the squad by formation slot (save.toml's `grid`): starter, backup, then third (to sell or loan out) by position score, then the
   youth (`youth_age` and under) by vs Age, so the pipeline and who's blocking the next intake show at a glance
3. **elsewhere**: every other player they've looked at
4. **last**: just the players from the most recent import (e.g. one transfer search)
5. **filters**: per position, the squad's best players and suggested minimums for FM's player search
6. **charts**: players with a match rating (a league-wide search) by position: role scores, score vs wage,
   score vs average rating, and Acceleration, Pace, Jumping Reach or Agility (a toggle; Agility is keepers only) by position and vs rating, with the squad overlaid
7. **staff**: every staff member observed, scored for each role (manager, coach groups, scout, physio…)
8. **last_staff**: just the staff from the most recent staff import
9. **staff_filters**: per staff role, the club's best staff and suggested minimums for FM's staff search
0. **settings**: what's in `config.toml` and the save's `save.toml`

Runs on macOS, Windows and Linux: stdlib Python 3.11+ only (`python3` here; on Windows it may be `python` or `py`).

## Files

| Path | Purpose |
|---|---|
| `config.toml` | This computer's settings: `active_save` (the save being worked on; only ever touch that save), `exports_dir` (where the user saves Print Screen files), `currency`. Gitignored; `python3 score.py init` writes it, `config.example.toml` shows it. |
| `saves/<save>/save.toml` | `weights` (→ `weights/<name>.toml`), `managed_club` (exactly as FM shows it), `short_name` (page 1 label), `division` (the managed club's, as FM shows it; page 6's default), `last_batch` (obs files for page 4), `last_staff_batch` (staff files for page 8), `last_staff_names` (staff already observed to add to page 8), `loan` (name → `in`/`out`/`trial`: FM12 exports don't show the coloured names), `youth_age`, `grid` (page 2's formation slots: `label`, weights `pos`, `left = true` for left-footed only), `grid_pins` (player → slot label), `grid_senior` (youngsters moved up to the senior columns), `grid_youth` (intake players kept: youth columns), `grid_exclude` (left off the grid) `released` (players gone since the latest squad screen) `signed` (players joined since) `recalled` (back from loan since) and `aliases` (a name FM cut off in an obs file → the full name). |
| `saves/<save>/obs/*.csv` | Observations: `<YYYY-MM-DD>_<source>_<view>.csv`, one per exported list. Append-only. |
| `saves/<save>/staff/*.csv` | Staff observations: `<YYYY-MM-DD>_<source>.csv` (`search-coach`). Append-only. |
| `weights/fm12.toml` | Position weights (`[outfield.*]`, `[gk]`), age benchmarks, and staff scoring: `[staff.<role>]` (the role's column label, then attribute weights) and `[staff_names]`. FM12 staff attributes are numbers, so no `[staff_words]`. |
| `weights/fm12_notes.md` | Notes on the weights: FM27 → FM12 renames, training categories, how to calibrate. |
| `fm12export.py` | Reads FM12 Print Screen files (pipe tables in .txt/.rtf, or .html tables) and writes the CSVs. Column heading map (abbreviations and full names) lives here. |
| `score.py` | `python3 score.py [--save S] [--open PAGE]` → `out/<save>/*.html`. Also `init` (first-time setup), `exports` (list new export files) and `import` (read them). Stdlib only. |
| `tests/` | `python3 -m unittest discover tests`: parsing and an end-to-end build, from the files in `tests/samples`. |
| `template.html` | Every page but charts. Its `?` overlay is the reference for keys and filter syntax. |
| `charts.html` | Page 6: hand-drawn SVG charts. |
| `theme.css` | Omarchy / Tokyo Night theme, inlined into every page. |
| `out/` | Generated; gitignored. |
| `README.md` | For people: what this is and how to set up a new save. |
| `CLAUDE.md` | Just imports this file. |

## Adding exports

The user says something like "new exports" (or "new screenshots": same thing here).

1. **Find them:** `python3 score.py exports` lists Print Screen files (.txt, .rtf, .html) from the last 10 minutes
   in `exports_dir` (`--minutes N` to look further back).
2. **Ask for FM's in-game date** if the user hasn't said it: the files don't contain it. FM shows it day first:
   `1/7/2012` → `2012-07-01`. Ask what each list is if it isn't clear: their squad (`--source <club slug>`, the
   managed club's short name) or a search (`--source search-<what>`, e.g. `search-cb`, `search-league-one`).
   Youth or reserve squads: `<club>-u18s`, `<club>-reserves` (see PARTIAL_SQUAD). A youth intake: `search-youth-intake`.
3. **Import:** `python3 score.py import [FILES...] --date YYYY-MM-DD --source <source>` (no files = those from the last
   10 minutes). Different lists need separate runs with their own `--source`. It:
   - writes `obs/<date>_<source>_outfield.csv` and/or `_gk.csv` (keepers by the Position column, else by their
     GK vs outfield attributes), or `staff/<date>_<source>.csv` for a staff list (recognised from staff-only columns;
     `--staff` forces it). The same date + source + view merges into the existing file.
   - fills Club with `managed_club` on a squad screen (no Club column there).
   - refuses a date earlier than the save's latest (a different save?) unless `--force`.
   - sets `last_batch` / `last_staff_batch` in save.toml, clears `last_names` / `last_staff_names`, scores, and opens the page.
4. **Check the output:** it prints `ignored columns`. If an attribute the weights need is among them, its heading
   isn't in `fm12export.py`'s maps: add the abbreviation there (and a test). If scoring fails with "not enough
   attributes", the FM view is missing the columns it lists: tell the user which to add.
5. Commit the save data: `git -C saves add -A && git -C saves commit -m "<save>: <what> <date>"`.
6. Report notable players: top of the new batch, big changes since a player's previous observation.

A shortlist that's just names of players already observed: set `last_names = [...]` in save.toml instead.

Values: attributes are numbers; an unscouted range `12-15` becomes 13.5; `-` is blank (the previous value carries
forward). Wages per year or month are converted to per week. `Left Foot` words (or a 1–20 number, or Preferred
Foot: Left = Very Strong, Either = Strong) decide Left.

## Staff

FM12 staff attributes are 1–20 numbers. Staff scoring: role score = Σ(value × weight) / Σ(weights). Each
`[staff.<label>]` table in the weights file is a role: the label is its column, and `[staff_names]` gives its full
name (shown on page 9). A new role needs both. Words still work if a weights file has `[staff_words]` (later FMs).

## Starting a new save

The user says "help me set up a new save", wants another save, or there's no `config.toml` yet: follow
`.claude/skills/new-save/SKILL.md`.

"Switch to my <club> save" = set `active_save`, run `score.py --open squad`.

If FM renames an attribute, use the new name in the CSV header and in the weights file.

## Scoring

- **Position score** = Σ(attribute × weight) / Σ(weights), on FM's 1–20 scale. Outfield players get
  every `[outfield.*]` position, keepers (anyone in a `gk` observation) only `GK`. **Best** = the highest.
- **vs Age** = best ÷ `age_benchmark` for their age (clamped to the table's ends); 100% = on track.
- **Over time:** each attribute is its latest known value; club, age, wage and value come from the latest
  observation. Enter/double-click a player for their history by date.
- **Left** = yes for Fairly Strong or better (`LEFT_FOOTED` in `score.py`).
- **Left the club:** a managed-club player missing from the latest squad screen (non-`search-` file) moves to
  elsewhere as `left <club>`. A youth or reserve squad screen (source ending `-u18s`, `-u21s`, `-reserves`: `PARTIAL_SQUAD`)
  shows only part of the club, so it updates its players but doesn't count as the squad screen. The user saying a player's gone ("sold X", "released X") before the next squad screen: add them
  to `released = [...]` in save.toml (name as in the obs files); don't edit obs files.
  Likewise a signing ("signed X") goes in `signed = [...]`: they count as the managed club's until a newer squad screen. A player back from loan ("recalled X") goes in `recalled = [...]`: clears their `out` flag.
  When a new squad screen comes in, empty `released`, `signed` and `recalled`.
- **Loan** flags show next to names, from the latest observation that has a `Loan` column. Filter with `loan-in` / `loan-out` / `trial`.
- **Rating / minutes / division:** from the latest observation only (they're per season); rating and minutes show on elsewhere and last.
- **Charts page:** players rated in their latest observation, grouped by best role (or everyone at every role).
  Dropdowns pick the division (the baseline, blue) and a club to highlight (orange): the managed club's squad
  screen, or any club in that division. Defaults: save.toml's `division` and `managed_club`.
  r = correlation over the league players; the dashed line is their least-squares fit (on log wage for wage).
- **Grid page:** players are placed best first (by Score), each at their best position in the formation: its first
  free Starter, else Backup, else Third. Third holds any number, spread over that position's slots: players to sell or
  loan out. A left-footer prefers the left-footed slot. Senior = older than `youth_age`, by position score, with vs Age
  for those `GRID_PCT_AGE` (24) and under; youth by that position's score ÷ age benchmark. Out-on-loan players aren't placed.
  The latest youth intake (players in the newest obs files whose source contains `intake`, e.g. `search-youth-intake`)
  gets its own Intake columns, placed like the youth, until a squad screen shows them (then they're youth, or gone) or they're in `grid_youth` (the user's "keep X": youth columns now). With no intake, those columns are hidden.
  `grid_pins` in save.toml (`"Full Name" = "slot label"`) overrides a player's slot: the user's own calls on who plays where. `{ slot = "M C", col = "third" }` also fixes the column, and `row = 2` picks the second slot of that label (rows counted down the grid)
  (starter / backup / third); those players are placed first. `{ col = "third" }` alone: their best position. A pinned player out
  on loan is placed too. `grid_exclude` leaves players off the grid altogether (e.g. contracts running out). Everyone still goes in by score, but unpinned
  players avoid (at the same depth) slots a pinned player is still to fill.
- **Filters page:** the squad's top 3 per position (top 1 for GK). **Search ≥** = their rounded average
  for attributes weighted ≥ 2 (`SEARCH_MIN_WEIGHT`), for use as minimums in FM's search.
- **Staff filters page:** the same per staff role: the top 3 of the managed club's staff (at the club in its latest staff
  screen) by role score. **Search ≥** is a number (FM12 searches staff by number).

## Conventions

- Two git repos. The code repo (this folder) is on GitHub and ignores `saves/`, `config.toml` and `out/`.
  `saves/` is its own git repo, local only, never pushed: the user's save data stays private. Commit data there
  (`git -C saves …`) and code here, separately. Never add personal details (email, real save names) to the code repo.
- Display: scores `0.0`, vs Age `xx%`.
- In `weights/*.toml`, quote keys with `/` or spaces: `[outfield."WB/6"]`, `"First Touch" = 1`.
- Stdlib Python, no build step, no dependencies. Run the tests after changing `fm12export.py` or `score.py`.
- Keep credit to jamiebolden/fm-scoring (MIT) in README and LICENSE.
