"""Compare the packaged offline corpus with the canonical server behavior."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
CLI_PATH = ROOT / "plugins" / "bilam-standalone" / "skills" / "bilam-study" / "scripts" / "bilam_cli.py"
spec = importlib.util.spec_from_file_location("bilam_cli", CLI_PATH)
offline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(offline)


class StandalonePluginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from rag_engine import RAGEngine
        from text_stats import TextStats

        cls.rag = RAGEngine()
        cls.stats = TextStats(cls.rag)

    def test_packaged_corpus_and_archive(self):
        data = offline.catalog()
        self.assertEqual(data["documents"], self.rag.count())
        self.assertEqual(len(data["parashot"]), 54)
        self.assertEqual(sum(1 for _ in offline.source_rows(data)), self.rag.count())
        archive_path = ROOT / "dist" / "bilam-standalone.zip"
        self.assertLessEqual(archive_path.stat().st_size, 100_000_000)
        with zipfile.ZipFile(archive_path) as archive:
            self.assertIn("plugin.json", archive.namelist())
            self.assertFalse(any(name.endswith("mcp.json") for name in archive.namelist()))
            self.assertEqual(archive.testzip(), None)

    def test_search_matches_server_bm25(self):
        for query, parasha in (("בלעם", "פרשת בלק"), ("אברהם", None)):
            expected = self.rag.search(query, n=6, parashot=[parasha] if parasha else None)
            actual = offline.search(query, parasha, 6)
            self.assertEqual([source["text"] for source in actual["sources"]], expected["documents"][0])
            self.assertEqual([source["parasha"] for source in actual["sources"]], [meta["parasha"] for meta in expected["metadatas"][0]])

    def test_word_counts_and_stats_match_server(self):
        for parasha in ("פרשת בלק", None):
            for match_type in ("exact_word", "substring"):
                expected = self.stats.count_word("ברכה", match_type, parasha=parasha)
                actual = offline.count_word("ברכה", match_type, parasha=parasha)
                self.assertEqual(actual["total_occurrences"], expected["total_occurrences"])
                self.assertEqual(actual["verses_count"], expected["verses_count"])
        self.assertEqual(offline.parasha_stats("פרשת בלק"), self.stats.get_parasha_stats("פרשת בלק"))

    def test_word_export_contains_source_and_rtl(self):
        source = offline.search("בלעם", "פרשת בלק", 1)["sources"][0]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bilam.docx"
            offline.write_docx(path, "בלעם", [source])
            with zipfile.ZipFile(path) as archive:
                document = archive.read("word/document.xml")
                ElementTree.fromstring(document)
                self.assertIn(source["source_label"].encode("utf-8"), document)
                self.assertIn(b"w:bidi", document)


class ArchiveSmokeTests(unittest.TestCase):
    def test_extracted_zip_runs_without_server_or_dependencies(self):
        archive_path = ROOT / "dist" / "bilam-standalone.zip"
        with tempfile.TemporaryDirectory() as directory:
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(directory)
            script = Path(directory) / "skills" / "bilam-study" / "scripts" / "bilam_cli.py"
            result = subprocess.run([sys.executable, str(script), "list"], capture_output=True, text=True, encoding="utf-8", check=True)
            self.assertEqual(json.loads(result.stdout)["documents"], 184977)
            result = subprocess.run([sys.executable, str(script), "search", "בלעם", "--parasha", "בלק", "--limit", "1"], capture_output=True, text=True, encoding="utf-8", check=True)
            self.assertEqual(json.loads(result.stdout)["count"], 1)


if __name__ == "__main__":
    unittest.main()
