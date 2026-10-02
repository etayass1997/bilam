"""Smoke-test the extracted mobile archive without relying on repository files."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile


ARCHIVE = Path(__file__).resolve().parents[1] / "dist" / "bilam-mobile-web.zip"


class MobilePackageTests(unittest.TestCase):
    def test_archive_runs_with_full_corpus(self):
        with tempfile.TemporaryDirectory() as directory:
            with ZipFile(ARCHIVE) as archive:
                self.assertIsNone(archive.testzip())
                archive.extractall(directory)
            code = (
                "import sys; sys.path.insert(0, 'backend'); import app; "
                "client=app.app.test_client(); "
                "assert client.get('/health').json['doc_count']==184977; "
                "assert client.get('/api/search', query_string={'query':'בלעם','parasha':'בלק'}).json['count']>0; "
                "assert client.get('/service-worker.js').status_code==200"
            )
            subprocess.run([sys.executable, "-c", code], cwd=directory, check=True)


if __name__ == "__main__":
    unittest.main()
