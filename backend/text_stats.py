"""
ניתוח טקסטואלי מדויק על פסוקי התורה של הפרשה (לא הפירושים) — ספירות מילים,
חיפוש מופעים ונתונים כמותיים אחרים. נועד לשמש כ-tool שקלוד יכול להפעיל
כשנדרשת תשובה מדויקת (לא ניחוש של מודל שפה) על "כמה פעמים מופיעה המילה X".
"""

import re

# טווח טעמים/ניקוד U+0591-U+05C7, בלי U+05BE (מקף) שמפריד בין מילים סמוכות
# (לדוגמה בֶּן־צִפּוֹר הן שתי מילים) ולכן לא נכון להסיר אותו.
NIQQUD_RE = re.compile(r"[֑-ֽֿ-ׇ]")
HEBREW_WORD_RE = re.compile(r"[א-ת]+")


def strip_niqqud(text):
    return NIQQUD_RE.sub("", text)


def _hebrew_tokens(text):
    return HEBREW_WORD_RE.findall(strip_niqqud(text))


class TextStats:
    def __init__(self, rag_engine):
        self.rag_engine = rag_engine

    def _verses(self):
        verses = [d for d in self.rag_engine.docs if d["metadata"].get("source_type") == "torah"]
        verses.sort(key=lambda d: (d["metadata"].get("chapter") or 0, d["metadata"].get("verse") or 0))
        return verses

    def count_word(self, word, match_type="exact_word"):
        target = strip_niqqud(word).strip()
        if not target:
            return {"error": "לא סופקה מילה לחיפוש"}

        matches = []
        total = 0
        for doc in self._verses():
            meta = doc["metadata"]
            tokens = _hebrew_tokens(doc["text"])
            if match_type == "substring":
                count = sum(1 for t in tokens if target in t)
            else:
                count = sum(1 for t in tokens if t == target)
            if count:
                total += count
                matches.append({
                    "ref_he": meta.get("ref_he"),
                    "chapter": meta.get("chapter"),
                    "verse": meta.get("verse"),
                    "count": count,
                    "verse_text": meta.get("verse_text_hebrew"),
                })

        return {
            "word": word,
            "match_type": match_type,
            "total_occurrences": total,
            "verses_count": len(matches),
            "matches": matches,
        }

    def get_parasha_stats(self):
        verses = self._verses()
        total_words = sum(len(_hebrew_tokens(d["text"])) for d in verses)
        chapters = sorted({d["metadata"].get("chapter") for d in verses if d["metadata"].get("chapter") is not None})
        return {
            "total_verses": len(verses),
            "total_words": total_words,
            "chapters": chapters,
        }


TOOLS = [
    {
        "name": "count_word_in_parasha",
        "description": (
            "מחזיר ספירה מדויקת ומבוססת-קוד (לא הערכה) של מספר הפעמים שמילה או רצף אותיות "
            "מופיעים בטקסט המקראי של הפרשה (פסוקי התורה בלבד, לא הפירושים), כולל רשימת כל "
            "הפסוקים שבהם המילה מופיעה. יש להשתמש בכלי זה לכל שאלה כמותית על מספר הופעות של "
            "מילה/שורש/צירוף בפרשה — אין לנחש או לסמוך על זיכרון."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "word": {
                    "type": "string",
                    "description": "המילה או רצף האותיות לחיפוש, בכתיב חסר ניקוד (הניקוד מוסר אוטומטית משני הצדדים בהשוואה).",
                },
                "match_type": {
                    "type": "string",
                    "enum": ["exact_word", "substring"],
                    "description": (
                        "exact_word (ברירת מחדל) — התאמה למילה שלמה בלבד. "
                        "substring — כל מופע של הרצף כתת-מחרוזת בתוך מילים, שימושי לחיפוש שורש."
                    ),
                },
            },
            "required": ["word"],
        },
    },
    {
        "name": "get_parasha_stats",
        "description": "מחזיר נתונים כמותיים בסיסיים על הפרשה כולה: מספר פסוקים, מספר מילים כולל, ופרקים כלולים.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def run_tool(text_stats, name, tool_input):
    if name == "count_word_in_parasha":
        return text_stats.count_word(
            tool_input.get("word", ""),
            tool_input.get("match_type", "exact_word"),
        )
    if name == "get_parasha_stats":
        return text_stats.get_parasha_stats()
    return {"error": f"כלי לא מוכר: {name}"}
