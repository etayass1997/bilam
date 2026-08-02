"""
שלב 2 — Ingestion: data/<parasha>/*.json -> backend/kb/kb_data.json

קורא את כל קבצי הפסוקים שנוצרו ע"י scripts/fetch_sefaria.py, ולכל פסוק
יוצר מסמך torah אחד + מסמך commentary נפרד לכל פירוש (אף פעם לא מאחד
כמה מפרשים למסמך אחד).

מודולרי לפרשות עתידיות: מריצים עם --parasha-dir עבור כל תיקיית פרשה
שנוצרה ב-data/, בלי לשנות את קוד ה-ingestion.

    python ingest.py --parasha-dir ../data/balak
"""

import argparse
import glob
import json
import os

from rag_engine import RAGEngine


def ingest_parasha_dir(engine, parasha_dir):
    verse_files = sorted(glob.glob(os.path.join(parasha_dir, "*.json")))
    if not verse_files:
        raise ValueError(f"לא נמצאו קבצי JSON בתיקייה: {parasha_dir}")

    verse_count = 0
    commentary_count = 0

    for path in verse_files:
        try:
            with open(path, encoding="utf-8") as f:
                verse_doc = json.load(f)
        except Exception as exc:
            print(f"דילוג על {path}: שגיאת קריאה ({exc})")
            continue

        parasha = verse_doc.get("perasha")
        chapter = verse_doc.get("chapter")
        verse = verse_doc.get("verse")
        verse_text = verse_doc.get("verse_text_hebrew", "")
        ref_he = verse_doc.get("ref_he", "")

        if not verse_text:
            continue

        torah_id = f"{parasha}_{chapter}_{verse}_torah"
        engine.add_document(
            doc_id=torah_id,
            text=verse_text,
            metadata={
                "parasha": parasha,
                "chapter": chapter,
                "verse": verse,
                "verse_text_hebrew": verse_text,
                "commentator_name": None,
                "source_type": "torah",
                "source_url": verse_doc.get("source_url"),
                "ref_he": ref_he,
            },
        )
        verse_count += 1

        for i, commentary in enumerate(verse_doc.get("commentaries", [])):
            text = commentary.get("commentary_text", "")
            if not text:
                continue
            commentary_id = f"{parasha}_{chapter}_{verse}_commentary_{i}"
            engine.add_document(
                doc_id=commentary_id,
                text=text,
                metadata={
                    "parasha": parasha,
                    "chapter": chapter,
                    "verse": verse,
                    "verse_text_hebrew": verse_text,
                    "commentator_name": commentary.get("commentator_name"),
                    "source_type": "commentary",
                    "source_url": commentary.get("source_url"),
                    "ref_he": ref_he,
                },
            )
            commentary_count += 1

    return verse_count, commentary_count


def main():
    parser = argparse.ArgumentParser(description="Ingest פרשת שבוע ל-KB של בלעם")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--parasha-dir", help="תיקיית data/<parasha> שנוצרה ע''י fetch_sefaria.py")
    group.add_argument("--all-data", help="תיקיית data המכילה את כל הפרשות; בונה KB נקי ומלא")
    args = parser.parse_args()

    engine = RAGEngine(load_existing=not bool(args.all_data))
    if args.all_data:
        # A complete rebuild must not retain stale documents from an older KB.
        engine.docs = []
        engine._doc_positions = {}
        parasha_dirs = sorted(
            entry.path for entry in os.scandir(os.path.abspath(args.all_data))
            if entry.is_dir() and any(name.endswith(".json") for name in os.listdir(entry.path))
        )
    else:
        parasha_dirs = [os.path.abspath(args.parasha_dir)]

    verse_count = commentary_count = 0
    for parasha_dir in parasha_dirs:
        verses, commentaries = ingest_parasha_dir(engine, parasha_dir)
        verse_count += verses
        commentary_count += commentaries
        print(f"{os.path.basename(parasha_dir)}: {verses} פסוקים + {commentaries} פירושים")
    engine.finalize()
    engine.save()

    print(f"הוטמעו {verse_count} פסוקים + {commentary_count} פירושים. סה''כ מסמכים: {engine.count()}")
    print(f"נשמר ב-{engine.kb_path}")


if __name__ == "__main__":
    main()
