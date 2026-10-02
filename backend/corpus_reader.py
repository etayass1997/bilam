"""Read the packaged corpus without loading every commentary into RAM."""

import importlib.util
from pathlib import Path


CLI_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugins" / "bilam-standalone" / "skills" / "bilam-study"
    / "scripts" / "bilam_cli.py"
)
spec = importlib.util.spec_from_file_location("bilam_corpus_cli", CLI_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Corpus reader is missing: {CLI_PATH}")
corpus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(corpus)
CATALOG = corpus.catalog()


class CorpusStats:
    def count_word(self, word, match_type="exact_word", parasha=None):
        return corpus.count_word(word, match_type, parasha)

    def get_parasha_stats(self, parasha):
        return corpus.parasha_stats(parasha)
