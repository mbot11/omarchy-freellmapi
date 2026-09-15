import importlib.machinery
import importlib.util
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

FIX = Path(__file__).parent / "fixtures"
COLLECT_PATH = Path(__file__).resolve().parents[1] / "bin" / "collect"
STATE_REL = Path("omarchy") / "io.github.mbot11.freellmapi" / "state.json"


def load_collect():
    loader = importlib.machinery.SourceFileLoader("collect", str(COLLECT_PATH))
    spec = importlib.util.spec_from_loader("collect", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def fixture_payload(url, key=None):
    mapping = {
        "/livez": "livez.json",
        "/readyz": "readyz.json",
        "/v1/providers": "providers.json",
        "/v1/quota-forecast": "quota.json",
        "/v1/models": "models.json",
    }
    for suffix, name in mapping.items():
        if url.rstrip("/").endswith(suffix):
            return json.loads((FIX / name).read_text())
    raise AssertionError("unexpected url")


class CollectWriteTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_collect()
        self._http = self.mod.http_get
        self._key = self.mod.load_key
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        env = patch.dict(os.environ, {"XDG_STATE_HOME": self.td.name})
        env.start()
        self.addCleanup(env.stop)
        self.mod.load_key = lambda: "test-unified-key"
        self.state_path = Path(self.td.name) / STATE_REL

    def tearDown(self):
        self.mod.http_get = self._http
        self.mod.load_key = self._key

    def test_writes_state_json_with_gateway_live(self):
        self.mod.http_get = fixture_payload
        rc = self.mod.main([])
        self.assertEqual(rc, 0)
        self.assertTrue(self.state_path.is_file())
        mode = self.state_path.stat().st_mode
        self.assertFalse(mode & stat.S_IROTH)
        data = json.loads(self.state_path.read_text())
        self.assertTrue(data["gateway"]["live"])

    def test_keeps_previous_and_marks_stale_on_http_error(self):
        self.mod.http_get = fixture_payload
        self.mod.main([])
        previous = json.loads(self.state_path.read_text())
        self.assertFalse(previous.get("stale"))

        def boom(url, key=None):
            raise RuntimeError("unreachable")

        self.mod.http_get = boom
        rc = self.mod.main([])
        self.assertEqual(rc, 0)
        self.assertTrue(self.state_path.is_file())
        data = json.loads(self.state_path.read_text())
        self.assertTrue(data["stale"])
        self.assertEqual(data["chat"]["total"], previous["chat"]["total"])
        self.assertTrue(data["gateway"]["live"])

    def test_http_get_puts_key_on_stdin_not_argv(self):
        calls = []

        class Result:
            returncode = 0
            stdout = '{"status":"ok"}'
            stderr = ""

        def fake_run(argv, input=None, capture_output=None, text=None):
            calls.append((list(argv), input))
            return Result()

        original = self.mod.subprocess.run
        self.mod.subprocess.run = fake_run
        try:
            secret = "test-unified-key"
            payload = self.mod.http_get("http://127.0.0.1:3001/v1/models", key=secret)
            self.mod.http_get("http://127.0.0.1:3001/livez")
        finally:
            self.mod.subprocess.run = original

        expected = ["curl", "-sS", "-m", "8", "-K", "-"]
        self.assertEqual(len(calls), 2)
        auth_argv, auth_in = calls[0]
        live_argv, live_in = calls[1]
        self.assertEqual(auth_argv, expected)
        self.assertEqual(live_argv, expected)
        self.assertNotIn(secret, auth_argv)
        self.assertIn("Authorization: Bearer " + secret, auth_in)
        self.assertIn("url=http://127.0.0.1:3001/v1/models", auth_in)
        self.assertNotIn("Authorization", live_in)
        self.assertIn("url=http://127.0.0.1:3001/livez", live_in)
        self.assertEqual(payload, {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
