import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".superpowers", "__pycache__", ".pytest_cache", "fixtures"}
SKIP_SUFFIXES = {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf"}
TEXT_SUFFIXES = {".py", ".qml", ".sh", ".js", ".json", ".toml", ""}

QUERY_KEY = "?" + "key="
SK_PREFIX = "sk" + "_"
FLA_PREFIX = "freellmapi" + "-"
TMP_PID = re.compile(r"/tmp/[^\"'\s]*\.pid")
SHELL_CURL = re.compile(r"""(os\.system|subprocess\.(?:call|run|Popen))\(\s*['\"]curl""")
CURL_H_AUTH = re.compile(r"""['\"]-H['\"].{0,80}Authorization""")
TOKEN_DIGIT = re.compile(r"(?:sk_|freellmapi-)\S*\d")
SHELL_TRUE = "shell" + "=" + "True"


def iter_source_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        # Plugin source + tests; skip design docs that quote forbidden patterns.
        if "docs" in path.parts:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != "collect":
            continue
        yield path


class SecurityGrepTests(unittest.TestCase):
    def test_no_key_leak_or_tmp_pid_or_argv_secrets(self):
        violations = []
        for path in iter_source_files():
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            rel = path.relative_to(ROOT).as_posix()
            if QUERY_KEY in text:
                violations.append(f"{rel}: query-string key")
            if TMP_PID.search(text):
                violations.append(f"{rel}: /tmp pid file")
            if SHELL_CURL.search(text):
                violations.append(f"{rel}: curl invoked as a shell string")
            if CURL_H_AUTH.search(text):
                violations.append(f"{rel}: Authorization header in curl argv")
            if SHELL_TRUE in text:
                violations.append(f"{rel}: subprocess " + SHELL_TRUE)
            if TOKEN_DIGIT.search(text):
                violations.append(f"{rel}: {SK_PREFIX}/" + FLA_PREFIX + " literal with a digit")
        self.assertEqual(violations, [], msg="\n".join(violations))


if __name__ == "__main__":
    unittest.main()
