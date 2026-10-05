import json, unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
from lib.normalize import normalize_state, MEDIA_INFER, CHAT_LIST_CAP

FIX = Path(__file__).parent / "fixtures"

class NormalizeTests(unittest.TestCase):
    def load(self, name):
        return json.loads((FIX / name).read_text())

    def test_counts_and_fusion(self):
        s = normalize_state(self.load("livez.json"), self.load("readyz.json"),
                            self.load("providers.json"), self.load("quota.json"),
                            self.load("models.json"))
        self.assertTrue(s["gateway"]["live"])
        self.assertEqual(s["chat"]["total"], 4)
        self.assertTrue(s["fusion"]["available"])
        self.assertEqual(s["chat"]["auto_available"], True)
        self.assertTrue(s["media"]["counts_unknown"])
        self.assertLessEqual(len(s["chat"]["models"]), CHAT_LIST_CAP)

    def test_keeps_previous_on_error(self):
        prev = normalize_state(self.load("livez.json"), self.load("readyz.json"),
                               self.load("providers.json"), self.load("quota.json"),
                               self.load("models.json"))
        s = normalize_state(None, None, None, None, None, previous=prev, error="unreachable")
        self.assertEqual(s["chat"]["total"], prev["chat"]["total"])
        self.assertTrue(s["stale"])
        self.assertEqual(s["error"], "unreachable")
        # livez/readyz could not be fetched: gateway flips to down.
        self.assertFalse(s["gateway"]["live"])
        self.assertFalse(s["gateway"]["ready"])
        # Non-status fields survive from the previous snapshot.
        self.assertEqual(s["gateway"]["version"], prev["gateway"]["version"])
        self.assertEqual(s["gateway"]["ready_upstreams"], prev["gateway"]["ready_upstreams"])
        # The rest of the previous snapshot is preserved.
        self.assertEqual(s["providers"], prev["providers"])
        self.assertEqual(s["quota"], prev["quota"])

    def test_error_rebuild_livez_ok_readyz_fail(self):
        prev = normalize_state(self.load("livez.json"), self.load("readyz.json"),
                               self.load("providers.json"), self.load("quota.json"),
                               self.load("models.json"))
        s = normalize_state(
            {"status": "ok", "version": "0.4.1", "uptime_s": 3600},
            None, None, None, None,
            previous=prev, error="quota unreachable",
        )
        self.assertTrue(s["gateway"]["live"])
        self.assertFalse(s["gateway"]["ready"])
        self.assertTrue(s["stale"])
        self.assertEqual(s["error"], "quota unreachable")
        self.assertEqual(s["gateway"]["version"], "0.4.1")

    def test_error_rebuild_livez_fail_readyz_ok(self):
        prev = normalize_state(self.load("livez.json"), self.load("readyz.json"),
                               self.load("providers.json"), self.load("quota.json"),
                               self.load("models.json"))
        s = normalize_state(
            None,
            {"status": "ok", "ready_upstreams": 3},
            None, None, None,
            previous=prev, error="livez unreachable",
        )
        self.assertFalse(s["gateway"]["live"])
        self.assertTrue(s["gateway"]["ready"])
        self.assertEqual(s["gateway"]["ready_upstreams"], 3)
        self.assertTrue(s["stale"])

    def test_string_false_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_state(self.load("livez.json"), self.load("readyz.json"),
                            {"providers": []}, {"pools": []},
                            {"data": [{"id": "bad", "available": "false"}]})

    def test_missing_providers_key_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_state(self.load("livez.json"), self.load("readyz.json"),
                            {}, {"pools": []}, {"data": []})

    def test_empty_provider_list_is_valid(self):
        s = normalize_state(self.load("livez.json"), self.load("readyz.json"),
                            {"providers": []}, {"pools": []}, {"data": []})
        self.assertEqual(s["providers"], [])
        self.assertFalse(s["stale"])

    def test_available_models_are_kept_when_catalog_exceeds_cap(self):
        rows = [{"id": f"bad-{i:03d}", "available": False} for i in range(80)]
        rows.append({"id": "good-later", "available": True})
        rows.extend([
            {"id": "auto", "available": True},
            {"id": "fusion", "available": True},
        ])
        s = normalize_state(self.load("livez.json"), self.load("readyz.json"),
                            {"providers": []}, {"pools": []}, {"data": rows})
        ids = [m["id"] for m in s["chat"]["models"]]
        self.assertEqual(s["chat"]["total"], 83)
        self.assertEqual(s["chat"]["available"], 3)
        self.assertIn("good-later", ids)
        self.assertLessEqual(len(ids), CHAT_LIST_CAP)
        self.assertTrue(s["chat"]["truncated"])
        self.assertEqual(ids[:2], ["auto", "fusion"])

    def test_quota_unknown_fields_do_not_exceed_state_budget(self):
        s = normalize_state(
            self.load("livez.json"), self.load("readyz.json"),
            {"providers": []},
            {"pools": [{"pool": "fixture", "remaining": 1, "limit": 2, "unused": "x" * 150000}]},
            {"data": []},
        )
        blob = json.dumps(s)
        self.assertNotIn("unused", blob)
        self.assertLess(len(blob.encode()), 100_000)

    def test_media_infer_cloudflare_groq_pollinations(self):
        s = normalize_state(self.load("livez.json"), self.load("readyz.json"),
                            self.load("providers.json"), self.load("quota.json"),
                            self.load("models.json"))
        mods = {i["modality"]: i["from"] for i in s["media"]["inferred"]}
        self.assertIn("cloudflare", mods["image"])
        self.assertIn("groq", mods["transcription"])
        self.assertIn("pollinations", mods["video"])

if __name__ == "__main__":
    unittest.main()
