import importlib
import io
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "coros_data.py"


def run_help(extra_env):
    env = os.environ.copy()
    for key in ("COROS_WEB_BASE", "COROS_MOBILE_BASE", "COROS_ALLOW_CUSTOM_BASE_URL"):
        env.pop(key, None)
    env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


class SecurityConfigTests(unittest.TestCase):
    def test_default_endpoints_are_global_coros_hosts(self):
        result = run_help({})
        self.assertEqual(result.returncode, 0, result.stderr)

        sys.path.insert(0, str(ROOT / "scripts"))
        coros_data = importlib.import_module("coros_data")
        self.assertEqual(coros_data.WEB_BASE, "https://teamapi.coros.com")
        self.assertEqual(coros_data.MOBILE_BASE, "https://api.coros.com")

    def test_custom_web_base_is_rejected_without_explicit_opt_in(self):
        result = run_help({"COROS_WEB_BASE": "https://example.com"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("COROS_WEB_BASE host must be teamapi.coros.com", result.stderr)

    def test_custom_mobile_base_is_rejected_without_explicit_opt_in(self):
        result = run_help({"COROS_MOBILE_BASE": "https://example.com"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("COROS_MOBILE_BASE host must be api.coros.com", result.stderr)

    def test_custom_base_is_allowed_with_explicit_opt_in(self):
        result = run_help(
            {
                "COROS_WEB_BASE": "https://example.com",
                "COROS_MOBILE_BASE": "https://api.example.com",
                "COROS_ALLOW_CUSTOM_BASE_URL": "1",
            }
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_write_env_value_creates_private_file(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        coros_data = importlib.import_module("coros_data")

        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".coros.env"
            coros_data.write_env_value("COROS_MOBILE_TOKEN", "abc'123", env_file=env_file)

            mode = stat.S_IMODE(env_file.stat().st_mode)
            self.assertEqual(mode, 0o600)
            self.assertEqual(env_file.read_text(encoding="utf-8"), 'export COROS_MOBILE_TOKEN=\'abc\'"\'"\'123\'\n')

    def test_write_env_value_rejects_readable_existing_file(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        coros_data = importlib.import_module("coros_data")

        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".coros.env"
            env_file.write_text("", encoding="utf-8")
            env_file.chmod(0o644)

            with redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    coros_data.write_env_value("COROS_MOBILE_TOKEN", "token", env_file=env_file)


class StaticSafetyTests(unittest.TestCase):
    def test_docs_do_not_reference_old_region_endpoints(self):
        text = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in ("README.md", "SKILL.md", "scripts/coros_data.py", "scripts/coros_web_login.js")
        )
        self.assertNotIn("teamcnapi", text)
        self.assertNotIn("apicn", text)
        self.assertNotIn("trainingcn", text)


if __name__ == "__main__":
    unittest.main()
