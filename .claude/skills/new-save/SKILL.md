---
name: new-save
description: Set up a new FM2012 save for this scoring tool (first-time setup, or another club). Use when the user says "help me set up a new save", wants to start another save, or there is no config.toml yet.
---

# Starting a new save

The user says "help me set up a new save", or there's no `config.toml` yet. Assume they aren't technical: plain
words, one step at a time, no jargon, and do the typing for them. `README.md` is what they've read.

1. **Check the tools:** `python3 --version` (Windows: `python` or `py`) must be 3.11+, and `git --version` must work.
   If either is missing, point them to README's "What you need" and wait.
2. **Ask, then write the settings yourself** (don't send them to `score.py init`: it's interactive):
   - the club they manage and its division, exactly as FM shows them in tables;
   - the folder they'll save FM's Print Screen files to (offer FM2012's own folder:
     `~/Documents/Sports Interactive/Football Manager 2012`);
   - the currency FM shows.

   Write `config.toml` (from `config.example.toml`: `active_save`, `exports_dir`, `currency`) and
   `saves/<slug of club>/save.toml` (`weights = "fm12"`, `managed_club`, `short_name`, `division`,
   `last_batch = []`, `last_staff_batch = []`), and create its `obs/` and `staff/` folders. If `saves/` isn't a git repo
   yet, `git init saves` (it stays local: their data isn't pushed with the code).
   Check the exports folder exists.
3. **FM views:** there are no ready-made FM2012 view files. Walk them through README's step 3: the columns for
   each view come from `weights/fm12.toml` (every attribute weighted in a position or staff role), plus Name, Club,
   Age, Left Foot, Wage, Value (and Position, which sorts keepers from outfielders).
4. **First export:** their squad screen with the outfield view: Ctrl+P → text file or web page, saved in the exports
   folder. Ask for FM's date, then follow "Adding exports" in AGENTS.md.
5. Commit the new save: `git -C saves add -A && git -C saves commit -m "<save>: new save"`.

Another save: same steps; the new save becomes `active_save`.
