"""Check that the clean forecast uses no market inputs or UI features."""
import ast
import math
from pathlib import Path
import unittest
from v6_baseball_totals import probabilities_for_line

ROOT=Path(__file__).resolve().parent
APP=ROOT/'v6_app'/'app.py'

class BaseballOnlyTests(unittest.TestCase):
    def test_clean_app_no_market_modules_or_ui(self):
        src=APP.read_text(encoding='utf-8')
        import_nodes=[n for n in ast.walk(ast.parse(src)) if isinstance(n,(ast.Import,ast.ImportFrom))]
        mods=[name.name for n in import_nodes for name in n.names] if False else []
        for node in import_nodes:
            if isinstance(node,ast.ImportFrom):mods.append(node.module or '')
            else:mods.extend(alias.name for alias in node.names)
        self.assertFalse(any(m.startswith(('v5_markets','v5_totals','market_backtest')) for m in mods))
        for old in ('ODDS_API_KEY','odds_cache','Sportsbook and exchange comparison',
                    'Kalshi YES contract','PrizePicks','Underdog','fetch_book_odds',
                    'v6_market_data','market odds','manual price check'):
            self.assertNotIn(old.lower(),src.lower())

    def test_display_uses_pure_baseball_module(self):
        src=(ROOT/'v6_display.py').read_text(encoding='utf-8')
        self.assertIn('from v6_baseball_totals import probabilities_for_line',src)
        self.assertNotIn('v5_totals',src)

    def test_half_run_distribution(self):
        d=probabilities_for_line({2:0.2,6:0.3,7:0.5},6.5)
        self.assertAlmostEqual(d['under'],.5)
        self.assertAlmostEqual(d['over'],.5)
        self.assertEqual(d['push'],0)

    def test_integer_threshold(self):
        d=probabilities_for_line({2:0.2,6:0.3,7:0.5},6)
        self.assertAlmostEqual(d['under'],.2)
        self.assertAlmostEqual(d['over'],.5)
        self.assertAlmostEqual(d['push'],.3)

    def test_invalid_probabilities(self):
        for pmf in ({1:.8},{1:-.1,2:1.1},{}):
            with self.assertRaises(ValueError): probabilities_for_line(pmf,6.5)

    def test_forecast_core_has_no_market_dependencies(self):
        core=(ROOT/'v4_workflow.py').read_text(encoding='utf-8')
        for old in ('v5_markets','fetch_book_odds','kalshi_contract_edge','market_price',
                    'ODDS_API_KEY','american_to_decimal'):
            self.assertNotIn(old,core)

if __name__=='__main__': unittest.main()
