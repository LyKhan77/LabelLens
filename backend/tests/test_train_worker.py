import unittest
from unittest.mock import patch

from backend import train_worker


class TrainWorkerTest(unittest.TestCase):
    def test_emit_traceback_streams_error_and_stack_lines(self):
        emitted = []

        def capture(event):
            emitted.append(event)

        with patch.object(train_worker, "emit", side_effect=capture):
            try:
                raise RuntimeError("boom")
            except RuntimeError as exc:
                train_worker.emit_traceback(exc, "train_runner")

        self.assertGreaterEqual(len(emitted), 2)
        self.assertEqual(emitted[0]["event"], "log_line")
        self.assertIn("[train_runner] boom", emitted[0]["line"])
        self.assertTrue(any("Traceback" in item["line"] for item in emitted[1:]))
        self.assertTrue(any("RuntimeError: boom" in item["line"] for item in emitted[1:]))


if __name__ == "__main__":
    unittest.main()
