"""Context-tiered prices in the savings report.
Run: python3 -m unittest discover tests -p 'test_savings_tiers.py'
"""
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "plugins/modelscout/skills/modelscout/scripts/savings.py"
spec = importlib.util.spec_from_file_location("ms_savings_tiers", SCRIPT)
sv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sv)

CHEAP = {"cost": {"input": 0.1, "output": 0.5, "cache_read": 0.01, "cache_write": 0.125},
         "tiers": [{"input": 0.5, "output": 2.5, "cache_read": 0.05, "cache_write": 0.625,
                    "tier": {"type": "context", "size": 100000}}]}
MAIN = {"cost": {"input": 3, "output": 15, "cache_read": 0.3, "cache_write": 3.75}}


def prices():
    p = sv.Prices()
    p.models = {"cheap-model": CHEAP, "main-model": MAIN}
    p.all = dict(p.models)
    return p


def u(i=0, o=0, cr=0, cw=0):
    return {"input": i, "output": o, "cache_read": cr, "cache_write": cw}


class TierTests(unittest.TestCase):
    def test_under_threshold_uses_base(self):
        # prompt = 50k + 40k = 90k <= 100k: base. 50k*.1 + 10k*.5 + 40k*.01 = 5000+5000+400 = 10400 / 1e6
        self.assertAlmostEqual(prices().call_cost("cheap-model", u(50000, 10000, 40000)), 0.0104)

    def test_over_threshold_uses_tier(self):
        # prompt = 60k + 50k = 110k > 100k: tier. 60k*.5 + 10k*2.5 + 50k*.05 = 30000+25000+2500 = 57500 / 1e6
        self.assertAlmostEqual(prices().call_cost("cheap-model", u(60000, 10000, 50000)), 0.0575)

    def test_exactly_threshold_is_base(self):
        self.assertAlmostEqual(prices().call_cost("cheap-model", u(100000)), 100000 * 0.1 / 1e6)

    def test_mixed_route_sums_per_call(self):
        calls = [u(50000, 10000, 40000), u(60000, 10000, 50000)]
        r = {"routed": "cheap-model", "usage": u(110000, 20000, 90000), "calls": calls}
        self.assertAlmostEqual(prices().route_cost("cheap-model", r), 0.0104 + 0.0575)

    def test_route_without_calls_uses_base(self):
        # Hermes-style totals: 110k in, 20k out, 90k cache read at base: 11000+10000+900 = 21900 / 1e6
        r = {"usage": u(110000, 20000, 90000)}
        self.assertAlmostEqual(prices().route_cost("cheap-model", r), 0.0219)

    def test_tier_missing_fields_fall_back_to_base(self):
        p = prices()
        p.models["t"] = p.all["t"] = {"cost": {"input": 2, "output": 10, "cache_read": 0.2, "cache_write": 2.5},
                                      "tiers": [{"input": 4, "output": 15, "cache_read": 0.4,
                                                 "tier": {"type": "context", "size": 1000}}]}
        # tier input 4, output 15, cache_read .4, cache_write from base 2.5: 1000*4 + 1000*15 + 1000*.4 + 1000*2.5 = 21900
        self.assertAlmostEqual(p.call_cost("t", u(1000, 1000, 1000, 1000)), 0.0219)

    def test_report_uses_calls_for_both_models_and_notes_tiers(self):
        calls = [u(50000, 10000, 40000), u(60000, 10000, 50000)]
        r = {"description": "x", "main": "main-model", "routed": "cheap-model", "usage": u(110000, 20000, 90000),
             "ms": 1000, "calls": calls}
        o = sv.report([r], prices())
        self.assertAlmostEqual(o["down"]["routed_cost"], 0.0104 + 0.0575)
        # main is flat: 110k*3 + 20k*15 + 90k*.3 = 330000+300000+27000 = 657000 / 1e6
        self.assertAlmostEqual(o["down"]["main_cost"], 0.657)
        self.assertTrue(o["tiered"])
        self.assertIn("Context-tiered prices applied per request", sv.render_text(o, 30))

    def test_flat_report_has_no_tier_clause(self):
        r = {"description": "x", "main": "main-model", "routed": "main-model", "usage": u(1), "ms": 0}
        o = sv.report([r], prices())
        self.assertFalse(o["tiered"])
        self.assertNotIn("Context-tiered", sv.render_text(o, 30))

    def test_subagent_usage_collects_calls(self):
        import json, tempfile
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.jsonl"
            rows = [{"type": "assistant", "message": {"id": f"m{i}", "model": "cheap-model",
                     "usage": {"input_tokens": 10 * (i + 1), "output_tokens": 1}}} for i in range(2)]
            rows.append(rows[0])  # duplicate message id is ignored
            f.write_text("\n".join(json.dumps(r) for r in rows))
            calls = []
            model, usage, _ = sv.subagent_usage(f, calls)
        self.assertEqual(usage["input"], 30)
        self.assertEqual([c["input"] for c in calls], [10, 20])


if __name__ == "__main__":
    unittest.main()
