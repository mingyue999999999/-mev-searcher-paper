import unittest
import re
from pathlib import Path

class ScheduleConfigTests(unittest.TestCase):
    def test_workflow_schedule_and_safety(self):
        text = Path("../.github/workflows/mev-searcher.yml").read_text(encoding="utf-8")
        for required in (
            "workflow_dispatch:", "schedule:", 'cron: "27,57 * * * *"',
            'timezone: "Etc/UTC"', "group: mev-searcher-paper-account",
            ".github/heartbeat/mev.txt",
            "github.event_name != 'pull_request'",
        ):
            self.assertIn(required, text)
        self.assertNotIn(".github/hourly-fallback-trigger.txt", text)

    def test_official_actions_use_node24_compatible_majors(self):
        text = Path("../.github/workflows/mev-searcher.yml").read_text(encoding="utf-8")
        for action, minimum in (("checkout", 5), ("setup-python", 6), ("upload-artifact", 6)):
            match = re.search(rf'uses:\s*actions/{action}@v(\d+)', text)
            self.assertIsNotNone(match)
            self.assertGreaterEqual(int(match.group(1)), minimum)

    def test_queued_writer_reads_current_main_and_pr_keeps_its_sha(self):
        text = Path("../.github/workflows/mev-searcher.yml").read_text(encoding="utf-8")
        checkout_match = re.search(r'uses:\s*actions/checkout@v(\d+)(.*?)(?=\n      - |\Z)', text, re.S)
        self.assertIsNotNone(checkout_match)
        self.assertGreaterEqual(int(checkout_match.group(1)), 5)
        checkout = checkout_match.group(2)
        self.assertIn('fetch-depth: 0', checkout)
        self.assertIn("ref: ${{ github.event_name != 'pull_request' && github.ref == 'refs/heads/main' && 'main' || github.sha }}", checkout)
        self.assertIn("if: github.ref == 'refs/heads/main' && github.event_name != 'pull_request' && success()", text)
        self.assertIn('cancel-in-progress: false', text)
        self.assertNotIn('git push --force', text)

if __name__ == "__main__":
    unittest.main()
