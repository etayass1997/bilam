"""Deterministic counts over Torah verses in the local source corpus."""

import re

# Strip Hebrew accents and niqqud but retain maqqef as a word separator.
NIQQUD_RE = re.compile(r"[֑-ֽֿ-ׇ]")
HEBREW_WORD_RE = re.compile(r"[א-ת]+")


def strip_niqqud(text):
    return NIQQUD_RE.sub("", text)


def _hebrew_tokens(text):
    return HEBREW_WORD_RE.findall(strip_niqqud(text))


class TextStats:
    def __init__(self, rag_engine):
        self.rag_engine = rag_engine

    def _verses(self, parasha=None):
        verses = [d for d in self.rag_engine.docs if d["metadata"].get("source_type") == "torah"]
        if parasha:
            verses = [d for d in verses if d["metadata"].get("parasha") == parasha]
        verses.sort(key=lambda d: (d["metadata"].get("chapter") or 0, d["metadata"].get("verse") or 0))
        return verses

    def count_word(self, word, match_type="exact_word", parasha=None, max_matches=25):
        target = strip_niqqud(word).strip()
        if not target:
            return {"error": "לא סופקה מילה לחיפוש"}

        matches = []
        total = 0
        for doc in self._verses(parasha):
            meta = doc["metadata"]
            tokens = _hebrew_tokens(doc["text"])
            if match_type == "substring":
                count = sum(1 for token in tokens if target in token)
            else:
                count = sum(1 for token in tokens if token == target)
            if count:
                total += count
                matches.append({
                    "ref_he": meta.get("ref_he"),
                    "parasha": meta.get("parasha"),
                    "chapter": meta.get("chapter"),
                    "verse": meta.get("verse"),
                    "count": count,
                    "verse_text": meta.get("verse_text_hebrew"),
                })

        return {
            "word": word,
            "match_type": match_type,
            "parasha": parasha,
            "total_occurrences": total,
            "verses_count": len(matches),
            "matches": matches[:max_matches],
            "matches_truncated": len(matches) > max_matches,
        }

    def get_parasha_stats(self, parasha):
        verses = self._verses(parasha)
        total_words = sum(len(_hebrew_tokens(doc["text"])) for doc in verses)
        chapters = sorted({doc["metadata"].get("chapter") for doc in verses if doc["metadata"].get("chapter") is not None})
        return {
            "parasha": parasha,
            "total_verses": len(verses),
            "total_words": total_words,
            "chapters": chapters,
        }
