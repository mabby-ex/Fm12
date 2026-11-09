# FM2012 weights: notes and calibration

`fm12.toml` holds every weight `score.py` uses. Score = Σ(attribute × weight) / Σ(weights), on FM's 1–20 scale.

## Players

Taken from the FM2027 weights in [jamiebolden/fm-scoring](https://github.com/jamiebolden/fm-scoring), with FM2012's
attribute names:

| FM2027 | FM2012 |
|---|---|
| Jumping Reach | Jumping |
| Aerial Reach | Aerial Ability |
| Leadership | Influence (unweighted) |

FM2012's match engine is known for rewarding Pace and Acceleration heavily, which the FM27 weights already do, so
they're a reasonable start. They haven't been tested against FM2012 yet.

**To calibrate:** compare scores with how players actually perform in your save (Av Rat over a season on the
charts page, page 6). If a position's top scorers keep underperforming, change that position's weights.

## Staff

FM2012 shows staff attributes as 1–20 numbers, so no word table is needed (later FMs show words).

FM2012's staff attributes:

| Group | Attributes |
|---|---|
| Coaching | Attacking, Defending, Fitness, Goalkeepers, Mental, Tactical, Technical, Working With Youngsters |
| Mental | Adaptability, Determination, Level of Discipline, Man Management, Motivating |
| Knowledge | Judging Player Ability, Judging Player Potential, Tactical Knowledge |
| Medical | Physiotherapy |

Changes from the FM27 roles:

- **Coaches** are scored for FM2012's nine training categories instead of FM27's coaching groups. Each category
  uses its coaching attribute(s) at a total weight of 8, plus Determination, Level of Discipline and Motivating at 2
  and Working With Youngsters at 1:

  | Category | Coaching attributes |
  |---|---|
  | Strength, Aerobic | Fitness |
  | Goalkeeping | Goalkeepers |
  | Tactics | Tactical |
  | Ball Control | Technical + Mental |
  | Defending | Defending + Tactical |
  | Attacking | Attacking + Tactical |
  | Shooting | Technical + Attacking |
  | Set Pieces | Technical + Mental |

  This is the commonly quoted FM11/FM12 community rule of thumb, not something SI published.
- **No** Sports Scientist, Performance Analyst or Set Piece Coach (FM2012 doesn't have those jobs), and no
  Authority, Possession, Set Pieces, Sports Science or Analysing Data attributes.
- **Head of Youth Development** becomes **Youth** (youth coach / under-18 manager).
- **People Management** is Man Management; **Level of Discipline** is back.

**To calibrate:** FM2012's **Training → Coaches** screen shows each coach's stars for each category. Export
your coaches with the staff view, then compare their Str/Aer/…/Set scores with the stars. If the order disagrees,
change the category's weights.
