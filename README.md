# FM2012 player and staff scoring

A helper for **Football Manager 2012**. It gives every player you look at a score for each position, and every
staff member a score for each job, so you can compare them at a glance: your squad, transfer targets, whole
leagues and your staff. It remembers every player you've seen, so you can also follow how they develop over the
seasons.

This is an FM2012 version of [jamiebolden/fm-scoring](https://github.com/jamiebolden/fm-scoring), which was
made for FM2027. The pages and scoring work the same way. The difference is how the data gets in: FM2012 can
**print any list to a file** (Print Screen), so this version reads those files directly. Nobody has to read
screenshots or type numbers in.

Made for Windows; also runs on Mac and Linux.

---

## What you need

- **Football Manager 2012.**
- **Python**, version 3.11 or newer. It's free: download it from [python.org/downloads](https://www.python.org/downloads/).
  On the installer's first screen, tick **"Add python.exe to PATH"**.
- **Git**, to download this project: [git-scm.com](https://git-scm.com/downloads). Click Next through the installer.
- **Optional: Claude Code** ([claude.com/claude-code](https://claude.com/claude-code)). It can run the commands
  below for you if you'd rather type "new exports" than use the terminal.

---

## Setting up (about 10 minutes)

### 1. Download this project

Press the Windows key, type **PowerShell**, and press Enter. Then type these lines one at a time, pressing Enter
after each:

```
cd Documents
git clone https://github.com/mabby-ex/Fm12.git
cd Fm12
```

### 2. Create your save

```
python score.py init
```

It asks a few questions:

- **The folder you'll save FM's Print Screen files to.** The default is FM2012's own folder,
  `Documents\Sports Interactive\Football Manager 2012`. Any folder works, as long as you save your exports there.
- **The currency** FM shows wages in (£, €, $…).
- **The club you manage**, exactly as FM shows it in its tables, e.g. "Man Utd", not "Manchester United".
- **Your club's division**, again as FM shows it, e.g. "npower Championship".

If `python` isn't found, try `py` instead.

### 3. Set up your views in FM2012

FM only exports the columns your view shows, so make views with these columns. In a player list, click the
**View** button above it, then **Customise Current View**, add the columns, and **Save** the view with a name.

| View | Use it on | Columns |
|---|---|---|
| `scoring outfield` | your squad, player searches, shortlists | Name, Club, Age, Left Foot (or Preferred Foot), Wage, Value, and the outfield attributes below |
| `scoring gk` | the same, for goalkeepers | Name, Club, Age, Wage, Value, and the goalkeeping attributes below |
| `scoring league` | a player search of a whole division (feeds the charts page) | `scoring outfield` plus Mins, Av Rat and Division |
| `scoring staff` | staff search, your staff list | Name, Club, Age, Job, and every staff attribute |

- **Outfield:** Acceleration, Anticipation, Composure, Decisions, Dribbling, Finishing, First Touch, Heading,
  Jumping, Off The Ball, Pace, Passing, Positioning, Stamina, Strength, Tackling, Teamwork and Work Rate.
- **Goalkeepers:** Acceleration, Aerial Ability, Agility, Anticipation, Command of Area, Communication, Composure,
  Concentration, Decisions, Handling, Kicking, One on Ones, Passing, Positioning, Reflexes and Throwing.
  Add a **Position** column too: then a mixed list of keepers and outfielders is sorted out automatically.
- **Staff:** Attacking, Defending, Fitness, Goalkeepers, Mental, Tactical, Technical, Working With Youngsters,
  Adaptability, Determination, Level of Discipline, Man Management, Motivating, Judging Player Ability,
  Judging Player Potential, Tactical Knowledge and Physiotherapy.

Extra columns are fine: they're ignored.

### 4. Export your squad

1. In FM, open your **squad** screen with the `scoring outfield` view.
2. Press **Ctrl + P** (or use FM's menu, top right: **Print Screen**). Choose **Text file** or **Web page**
   and save it in your exports folder.
3. Note **FM's date** (top of the screen). The files don't include it.
4. Back in PowerShell:

   ```
   python score.py import --date 2012-07-01 --source my-club
   ```

   Use FM's date, written year-month-day: FM's `1/7/2012` is `2012-07-01`. `--source` says what the list is:
   your squad is your club's short name (`my-club`); a search is `search-<anything>`, e.g. `search-cb`.

It reads every export saved in the last 10 minutes, saves the players, and opens the page in your browser. To read
particular files instead, name them: `python score.py import "C:\path\to\squad.txt" --date ... --source ...`.

---

## Using it

Whenever you want to add players: export the list in FM, then run `import` with FM's date. For example:

- **A transfer search:** `--source search-strikers`.
- **A shortlist or scouting list.**
- **A whole league:** a player search of one division with the `scoring league` view. That fills the charts page.
- **Staff:** a staff search with the `scoring staff` view: `--source search-coaches`. Staff lists are recognised
  from their columns.
- **Your squad again later:** every few months of game time, to see who's improving.

With Claude Code, start it in this folder (`claude`) and say **"new exports"**: it asks for FM's date and runs
the import for you.

FM2012's exports don't show whether a player is on loan (FM shows it as the colour of their name). To flag it, add
a `loan` table to your save's `save.toml`: `loan = { "Tom Hardwick" = "out", "Dean Cole" = "in" }`.

### The pages

Press the number keys to move between pages, and **?** on any page for its keyboard shortcuts.

| Key | Page | What's on it |
|---|---|---|
| 1 | Your squad | Every player at your club, scored for each position |
| 2 | Grid | Your formation: starter, backup and third for each slot, then your best youngsters for it |
| 3 | Elsewhere | Every other player you've exported |
| 4 | Last | Just the players from your latest import |
| 5 | Filters | Your best players per position, and minimum attributes to search FM for players better than them |
| 6 | Charts | Your squad against a whole league: scores, wages, ratings and pace |
| 7 | Staff | Every staff member you've exported, scored for each job |
| 8 | Last staff | Just the staff from your latest staff import |
| 9 | Staff filters | Your best staff per job, and minimum attributes to search FM for staff better than them |
| 0 | Settings | Your club, division and other settings |

Click a column heading to sort by it, and double-click a player to see their history. Type in the box at the top
to filter: for example, `age<=21 best=CB` shows centre-backs aged 21 and under.

The grid page and the formation settings work as in the original: see
[its README](https://github.com/jamiebolden/fm-scoring#your-formation-the-grid-page).

---

## How the scores work

Each position has a list of attributes that matter for it, each with a weight. A player's position score is the
weighted average of those attributes, on FM's 1–20 scale. **vs Age** compares their best score with what's
typical for their age: 100% means they're on track to be a good second-tier or lower top-flight player once fully
developed.

Staff are scored the same way, for each job: manager, assistant, youth coach, director of football, scout, physio,
and a coach for each of FM2012's nine training categories (Strength, Aerobic, Goalkeeping, Tactics, Ball Control,
Defending, Attacking, Shooting, Set Pieces).

The weights are in `weights/fm12.toml`, with notes in `weights/fm12_notes.md`. They start from the FM2027
project's weights, renamed for FM2012, and still need checking against FM2012 itself.

## Credits

Built on [fm-scoring](https://github.com/jamiebolden/fm-scoring) by Jamie Bolden (MIT licence; see `LICENSE`).
