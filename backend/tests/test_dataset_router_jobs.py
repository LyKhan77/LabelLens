import unittest

from backend.routers import dataset


class DatasetLabelJobStatusTest(unittest.TestCase):
    def tearDown(self):
        dataset.label_jobs.clear()

    def test_new_label_job_status_includes_item_log(self):
        job = dataset._new_job("demo")

        self.assertEqual(job["items"], [])


if __name__ == "__main__":
    unittest.main()
