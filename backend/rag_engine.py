"""
מנוע RAG מבוסס BM25 — אותו דפדפן כמו gordel/rag_engine.py, מותאם לבלעם:
כל מסמך הוא יחידה שלמה אחת (פסוק בודד או פירוש בודד), בלי chunking,
עם metadata מלא לציטוט מדויק (פרק, פסוק, מפרש, מקור).
"""

import gzip
import json
import os
import re

from rank_bm25 import BM25Okapi

KB_PATH = os.path.join(os.path.dirname(__file__), "kb", "kb_data.json.gz")
LEGACY_KB_PATH = os.path.join(os.path.dirname(__file__), "kb", "kb_data.json")


def _tokenize(text):
    return re.findall(r"[\w֐-׿]+", text.lower())


class RAGEngine:
    def __init__(self, kb_path=KB_PATH, load_existing=True):
        self.kb_path = kb_path
        self.docs = []  # list of {'id', 'text', 'metadata'}
        self._doc_positions = {}
        self._bm25 = None
        if load_existing:
            self._load()

    def _load(self):
        load_path = self.kb_path
        if not os.path.exists(load_path) and self.kb_path == KB_PATH and os.path.exists(LEGACY_KB_PATH):
            load_path = LEGACY_KB_PATH
        if os.path.exists(load_path):
            opener = gzip.open if load_path.endswith(".gz") else open
            with opener(load_path, "rt", encoding="utf-8") as f:
                self.docs = json.load(f)
            self._doc_positions = {doc["id"]: i for i, doc in enumerate(self.docs)}
            self._rebuild()

    def save(self):
        os.makedirs(os.path.dirname(self.kb_path), exist_ok=True)
        opener = gzip.open if self.kb_path.endswith(".gz") else open
        with opener(self.kb_path, "wt", encoding="utf-8", compresslevel=6) as f:
            json.dump(self.docs, f, ensure_ascii=False, separators=(",", ":"))

    def _rebuild(self):
        if self.docs:
            corpus = [_tokenize(d["text"]) for d in self.docs]
            self._bm25 = BM25Okapi(corpus)
        else:
            self._bm25 = None

    def add_document(self, doc_id, text, metadata):
        document = {"id": doc_id, "text": text, "metadata": metadata}
        position = self._doc_positions.get(doc_id)
        if position is None:
            self._doc_positions[doc_id] = len(self.docs)
            self.docs.append(document)
        else:
            self.docs[position] = document

    def finalize(self):
        """קוראים פעם אחת בסיום הוספת כל המסמכים (ingest), לפני save()."""
        self._rebuild()

    def search(self, query, n=6):
        if not self._bm25 or not self.docs:
            return {"documents": [[]], "metadatas": [[]]}
        tokens = _tokenize(query)
        scores = self._bm25.get_scores(tokens)
        top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n]
        docs = [self.docs[i]["text"] for i in top_idx if scores[i] > 0]
        metas = [self.docs[i]["metadata"] for i in top_idx if scores[i] > 0]
        return {"documents": [docs], "metadatas": [metas]}

    def count(self):
        return len(self.docs)
