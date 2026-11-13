"""Cloud-provider detection in discover-models.sh: env-presence only, no secrets leaked."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "plugins/modelscout/skills/modelscout/scripts/discover-models.sh"

CATALOG = {
    "azure": {"models": {"gpt-x": {"name": "GPT X", "release_date": "2025-01-01",
                                   "cost": {"input": 1, "output": 2}}}},
    "amazon-bedrock": {"models": {"anthropic.claude-y": {"name": "Claude Y", "release_date": "2025-02-02",
                                                         "cost": {"input": 3, "output": 4}}}},
    "google-vertex": {"models": {"gemini-z": {"name": "Gemini Z", "release_date": "2025-03-03",
                                              "cost": {"input": 5, "output": 6}}}},
}
SECRETS = ["sekret-azure-key", "myres.openai.azure.example", "sekret-aws-id", "sekret-aws-secret",
           "sekret-bearer", "my-private-profile", "my-gcp-project-123", "/path/to/sa-creds.json"]
SAFE_ENV = ("PATH", "LANG", "LC_ALL")


class CloudDetection(unittest.TestCase):
    def run_script(self, env_extra):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, True)
        os.makedirs(f"{home}/.claude")
        Path(f"{home}/.claude/model-catalog.json").write_text(json.dumps(CATALOG))
        # curl is replaced by a failing stub: any network use is a test failure.
        stub = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, stub, True)
        Path(f"{stub}/curl").write_text(f"#!/bin/sh\ntouch {home}/CURL_CALLED\nexit 7\n")
        os.chmod(f"{stub}/curl", 0o755)
        env = {k: v for k, v in os.environ.items() if k in SAFE_ENV}
        env["PATH"] = f"{stub}:{env.get('PATH', '/usr/bin:/bin')}"
        env["HOME"] = home
        env.update(env_extra)
        r = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(f"{home}/CURL_CALLED"), "network client was invoked")
        raw = Path(f"{home}/.claude/model-inventory.json").read_text()
        for s in SECRETS:
            self.assertNotIn(s, raw)
            self.assertNotIn(s, r.stdout + r.stderr)
        return json.loads(raw)["providers"], r.stdout

    def test_azure(self):
        p, out = self.run_script({"AZURE_OPENAI_API_KEY": "sekret-azure-key",
                                  "AZURE_OPENAI_ENDPOINT": "https://myres.openai.azure.example/"})
        self.assertEqual(list(p), ["azure"])
        m = p["azure"]["models"][0]
        self.assertEqual((m["id"], m["cost_per_1m"]["input"], m["release_date"]), ("gpt-x", 1, "2025-01-01"))
        self.assertIn("deployments not listed", p["azure"]["source"])
        self.assertIn("azure", out)

    def test_azure_alt_vars(self):
        p, _ = self.run_script({"AZURE_API_KEY": "sekret-azure-key", "AZURE_RESOURCE_NAME": "myres.openai.azure.example"})
        self.assertIn("azure", p)

    def test_bedrock_variants(self):
        for env in ({"AWS_BEARER_TOKEN_BEDROCK": "sekret-bearer"},
                    {"AWS_ACCESS_KEY_ID": "sekret-aws-id", "AWS_SECRET_ACCESS_KEY": "sekret-aws-secret"},
                    {"AWS_PROFILE": "my-private-profile"},
                    {"CLAUDE_CODE_USE_BEDROCK": "1"}):
            with self.subTest(env=list(env)):
                p, _ = self.run_script(env)
                self.assertEqual(list(p), ["bedrock"])
                self.assertEqual(p["bedrock"]["models"][0]["id"], "anthropic.claude-y")
                self.assertEqual(p["bedrock"]["models"][0]["cost_per_1m"]["output"], 4)

    def test_vertex_variants(self):
        for env in ({"GOOGLE_CLOUD_PROJECT": "my-gcp-project-123", "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/sa-creds.json"},
                    {"GOOGLE_VERTEX_PROJECT": "my-gcp-project-123", "CLAUDE_CODE_USE_VERTEX": "1"},
                    {"ANTHROPIC_VERTEX_PROJECT_ID": "my-gcp-project-123", "CLAUDE_CODE_USE_VERTEX": "1"}):
            with self.subTest(env=list(env)):
                p, _ = self.run_script(env)
                self.assertEqual(list(p), ["vertex"])
                self.assertEqual(p["vertex"]["models"][0]["id"], "gemini-z")

    def test_partial_signals_detect_nothing(self):
        for env in ({"AZURE_OPENAI_API_KEY": "sekret-azure-key"},
                    {"AZURE_OPENAI_ENDPOINT": "https://myres.openai.azure.example/"},
                    {"AWS_ACCESS_KEY_ID": "sekret-aws-id"},
                    {"AWS_SECRET_ACCESS_KEY": "sekret-aws-secret"},
                    {"CLAUDE_CODE_USE_BEDROCK": "0"},
                    {"GOOGLE_CLOUD_PROJECT": "my-gcp-project-123"},
                    {"GOOGLE_APPLICATION_CREDENTIALS": "/path/to/sa-creds.json"},
                    {"CLAUDE_CODE_USE_VERTEX": "1"}):
            with self.subTest(env=list(env)):
                p, out = self.run_script(env)
                self.assertEqual(p, {})
                self.assertIn("No provider API keys found", out)

    def test_no_keys_message_mentions_cloud_vars(self):
        _, out = self.run_script({})
        for name in ("AZURE_OPENAI_API_KEY", "AWS_PROFILE", "GOOGLE_APPLICATION_CREDENTIALS"):
            self.assertIn(name, out)


if __name__ == "__main__":
    unittest.main()
