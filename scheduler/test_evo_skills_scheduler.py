import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("evo_skills_scheduler.py")
SPEC = importlib.util.spec_from_file_location("evo_skills_scheduler", MODULE_PATH)
scheduler = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(scheduler)


class SchedulerCommandTests(unittest.TestCase):
    def test_build_claude_command_with_model(self):
        cmd = scheduler.build_agent_command(
            agent_name="greate-stocks-operator",
            command="go",
            executor="claude",
            model="claude-sonnet-4-6",
        )

        self.assertEqual(
            cmd,
            [
                "claude",
                "--model",
                "claude-sonnet-4-6",
                "-p",
                "/greate-stocks-operator go",
                "--print",
            ],
        )

    def test_build_opencode_command_with_model(self):
        cmd = scheduler.build_agent_command(
            agent_name="greate-stocks-operator",
            command="go",
            executor="opencode",
            model="opencode/minimax-m2.5-free",
        )

        self.assertEqual(
            cmd,
            [
                "opencode",
                "run",
                "-m",
                "opencode/minimax-m2.5-free",
                "/greate-stocks-operator go",
            ],
        )

    def test_build_opencode_command_with_absolute_path(self):
        cmd = scheduler.build_agent_command(
            agent_name="greate-stocks-operator",
            command="go",
            executor="/opt/homebrew/bin/opencode",
            model="opencode/minimax-m2.5-free",
        )

        self.assertEqual(
            cmd,
            [
                "/opt/homebrew/bin/opencode",
                "run",
                "-m",
                "opencode/minimax-m2.5-free",
                "/greate-stocks-operator go",
            ],
        )

    def test_load_configs_reads_agent_model(self):
        yaml_text = """
agent:
  name: sample-agent
  executor: opencode
  model: opencode/minimax-m2.5-free

schedules:
  - command: go
    cron: "0 8 * * *"
    description: "sample"
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            (config_dir / "sample-agent.yaml").write_text(yaml_text, encoding="utf-8")
            with mock.patch.object(scheduler, "CONFIGS_DIR", config_dir):
                configs = scheduler.load_configs()

        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]["model"], "opencode/minimax-m2.5-free")


if __name__ == "__main__":
    unittest.main()
