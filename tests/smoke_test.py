import unittest
from pathlib import Path

from core.orchestrator import MacroOrchestrator


class SmokeTests(unittest.TestCase):
    def test_orchestrator_snapshot_shape(self) -> None:
        orchestrator = MacroOrchestrator(Path(__file__).resolve().parents[1])
        snapshot = orchestrator.snapshot()
        self.assertIn("state", snapshot)
        self.assertIn("features", snapshot)
        self.assertIn("services", snapshot)


if __name__ == "__main__":
    unittest.main()
