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
