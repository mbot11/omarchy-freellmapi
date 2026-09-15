import importlib.machinery
import importlib.util
import json
import os
import stat
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
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


def serve_json(routes):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status, body = routes.get(self.path, (404, b"{}"))
            if isinstance(body, str):
                body = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def stop_server(server, thread):
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


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
        # Gateway was down when the error hit: the stale snapshot must show it.
        self.assertFalse(data["gateway"]["live"])
        self.assertFalse(data["gateway"]["ready"])

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

        expected = ["curl", "-sS", "-f", "-m", "8", "-K", "-"]
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

    def test_missing_key_keeps_previous_and_marks_stale(self):
        self.mod.http_get = fixture_payload
        self.mod.main([])
        previous = json.loads(self.state_path.read_text())
        self.assertFalse(previous.get("stale"))

        called = []

        def spy(url, key=None):
            called.append(url)
            return fixture_payload(url, key)

        self.mod.http_get = spy
        self.mod.load_key = lambda: None
        rc = self.mod.main([])
        self.assertEqual(rc, 0)
        self.assertEqual([u for u in called if "/v1/" in u], [])
        data = json.loads(self.state_path.read_text())
        self.assertTrue(data["stale"])
        self.assertEqual(data["chat"]["total"], previous["chat"]["total"])
        self.assertIn("missing FREELLMAPI_UNIFIED_KEY", data.get("error") or "")
        # livez/readyz answered ok before the key guard tripped: gateway stays up
        # (amber first-run case), only the /v1 set is unavailable.
        self.assertTrue(data["gateway"]["live"])
        self.assertTrue(data["gateway"]["ready"])

    def test_http_get_raises_on_401_json(self):
        server, thread = serve_json({"/v1/models": (401, b'{"error":"unauthorized"}')})
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/v1/models"
            with self.assertRaises(RuntimeError):
                self.mod.http_get(url, key="wrong-key")
        finally:
            stop_server(server, thread)

    def test_collect_marks_stale_on_non_2xx(self):
        self.mod.http_get = fixture_payload
        self.mod.main([])
        previous = json.loads(self.state_path.read_text())
        live = b'{"status":"ok","version":"test","uptime_s":1}'
        ready = b'{"status":"ok","ready_upstreams":1}'
        err = b'{"error":"unavailable"}'
        server, thread = serve_json({
            "/livez": (200, live),
            "/readyz": (200, ready),
            "/v1/providers": (503, err),
            "/v1/quota-forecast": (503, err),
            "/v1/models": (503, err),
        })
        try:
            cfg = self.state_path.parent / "config.json"
            cfg.parent.mkdir(parents=True, exist_ok=True)
            cfg.write_text(json.dumps({
                "baseUrl": f"http://127.0.0.1:{server.server_address[1]}",
            }))
            self.mod.http_get = self._http
            rc = self.mod.main([])
        finally:
            stop_server(server, thread)
        self.assertEqual(rc, 0)
        data = json.loads(self.state_path.read_text())
        self.assertTrue(data["stale"])
        self.assertEqual(data["chat"]["total"], previous["chat"]["total"])


if __name__ == "__main__":
    unittest.main()
