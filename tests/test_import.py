"""Tests for reading FM12 Print Screen exports and scoring them end to end.

    python3 -m unittest discover tests

The files in tests/samples are hand-made in the shape of FM12's exports. Swap in real exports as they come in.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import fm12export  # noqa: E402
import score  # noqa: E402

SAMPLES = HERE / "samples"


class ParseTest(unittest.TestCase):
    def test_squad_text(self):
        kind, rows, ignored = fm12export.parse(SAMPLES / "squad.txt")
        self.assertEqual(kind, "player")
        self.assertEqual([r["Name"] for r in rows], ["Tom Hardwick", "Luis Almeida", "Jack Ellison"])
        tom = rows[0]
        self.assertEqual(tom["attrs"]["Jumping"], 16)
        self.assertEqual(tom["attrs"]["Positioning"], 14)  # "Pos" is Positioning, not Position
        self.assertEqual(tom["Left Foot"], "Weak")
        self.assertIn("Inf", ignored)
        self.assertEqual([fm12export.is_keeper(r) for r in rows], [False, False, True])

    def test_search_html(self):
        kind, rows, _ = fm12export.parse(SAMPLES / "search.html")
        mats, dean = rows
        self.assertEqual(mats["Club"], "Malmö")
        self.assertEqual(mats["Left Foot"], "Very Strong")  # Preferred Foot: Left
        self.assertEqual((mats["Minutes"], mats["Rating"], mats["Division"]), ("1620", "7.12", "Allsvenskan"))
        self.assertEqual(dean["attrs"]["Acceleration"], 13.5)  # scouting range 12-15
        self.assertIsNone(dean["attrs"]["Dribbling"])  # "-": not known
        self.assertEqual(dean["Rating"], "")

    def test_staff_text(self):
        kind, rows, _ = fm12export.parse(SAMPLES / "staff.txt")
        self.assertEqual(kind, "staff")
        g = rows[0]
        self.assertEqual(g["attrs"]["Technical"], 10)  # Tec is Technical for staff
        self.assertEqual(g["attrs"]["Level of Discipline"], 14)
        self.assertEqual(g["attrs"]["Goalkeepers"], 3)

    def test_rtf(self):
        rtf = "{\\rtf1\\ansi{\\fonttbl{\\f0 Courier New;}}\\f0 | Name | Age | Acc | Pac | Sta |\\par | Ren\\'e9 Dubois | 20 | 14 | 15 | 12 |\\par}"
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.rtf"
            p.write_text(rtf, encoding="cp1252")
            _, rows, _ = fm12export.parse(p)
        self.assertEqual(rows[0]["Name"], "René Dubois")
        self.assertEqual(rows[0]["attrs"]["Pace"], 15)

    def test_money(self):
        self.assertEqual(score.money("£12,000 p/w"), 12000)
        self.assertEqual(score.money("£780K p/a"), 15000)
        self.assertEqual(score.money("£3.2M"), 3.2e6)
        self.assertIsNone(score.money("-"))


class EndToEndTest(unittest.TestCase):
    """Import the samples into a throwaway copy of the project and build every page."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for f in ("template.html", "charts.html", "theme.css"):
            shutil.copy(HERE.parent / f, self.tmp)
        shutil.copytree(HERE.parent / "weights", self.tmp / "weights")
        save = self.tmp / "saves" / "barnsley"
        save.mkdir(parents=True)
        (save / "save.toml").write_text('weights = "fm12"\nmanaged_club = "Barnsley"\nshort_name = "barnsley"\n'
                                        'division = "npower Championship"\nlast_batch = []\nlast_staff_batch = []\n')
        (self.tmp / "config.toml").write_text('active_save = "barnsley"\nexports_dir = "."\ncurrency = "£"\n')
        self.old = score.ROOT, score.CONFIG
        score.ROOT, score.CONFIG = self.tmp, self.tmp / "config.toml"

    def tearDown(self):
        score.ROOT, score.CONFIG = self.old
        shutil.rmtree(self.tmp)

    def run_import(self, *files, source, date="2012-07-01"):
        class A:
            pass
        a = A()
        a.files, a.date, a.source, a.staff, a.minutes, a.force, a.save = [str(SAMPLES / f) for f in files], date, source, False, 10, False, None
        return score.import_exports(a)

    def test_pages(self):
        self.run_import("squad.txt", source="barnsley")
        self.run_import("search.html", source="search-sweden")
        self.run_import("staff.txt", source="search-coaches")
        obs = sorted(p.name for p in (self.tmp / "saves/barnsley/obs").iterdir())
        self.assertEqual(obs, ["2012-07-01_barnsley_gk.csv", "2012-07-01_barnsley_outfield.csv",
                               "2012-07-01_search-sweden_outfield.csv"])
        toml = (self.tmp / "saves/barnsley/save.toml").read_text()
        self.assertIn('last_batch = ["2012-07-01_search-sweden_outfield.csv"]', toml)
        self.assertIn('last_staff_batch = ["2012-07-01_search-coaches.csv"]', toml)

        cfg, pages = score.build("barnsley", score.load_config())
        squad = {r["name"]: r for r in pages["squad"][1]}
        self.assertEqual(set(squad), {"Tom Hardwick", "Luis Almeida", "Jack Ellison"})
        self.assertEqual(squad["Jack Ellison"]["best"], "GK")
        self.assertEqual(squad["Tom Hardwick"]["wage"], 12000)
        self.assertEqual([r["name"] for r in pages["last"][1]], ["Mats Lindqvist", "Dean Cole"])
        staff = {r["name"]: r for r in pages["staff"][1]}
        self.assertEqual(staff["Paula Reyes"]["best"], "Str")  # a fitness coach is best at Strength / Aerobic
        self.assertEqual(staff["Paula Reyes"]["club"], "")  # no club: a free agent
        out = score.write_pages("barnsley", score.load_config(), cfg, pages)
        self.assertEqual(len(list(out.glob("*.html"))), len(score.PAGES))

    def test_earlier_date_refused(self):
        self.run_import("squad.txt", source="barnsley", date="2012-08-01")
        with self.assertRaises(SystemExit):
            self.run_import("squad.txt", source="barnsley", date="2012-07-01")


if __name__ == "__main__":
    unittest.main()
