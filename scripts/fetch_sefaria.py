"""
שלב 1 — שליפת טקסט תורה + פרשנות לפרשת שבוע מ-Sefaria API.

מריצים פעם אחת בזמן build (לא בזמן ריצה של הסוכן):
    python fetch_sefaria.py --parasha Balak
    python fetch_sefaria.py --parasha "Vaetchanan" --out-dir ../data

שם הפרשה הוא קונפיגורציה (פרמטר CLI) — לא קוד מקודד. אין הנחה בשום מקום
שקיימת רק פרשת בלק; הסקריפט פותר את טווח הפרקים/פסוקים דינמית מול ה-API
עבור כל שם פרשה שמועבר.
"""

import argparse
import html
import json
import logging
import os
import re
import time
import unicodedata

import requests

API_BASE = "https://www.sefaria.org/api"
USER_AGENT = "bilam-agent-fetcher/1.0 (+https://github.com/etayass1997/bilam-agent; one-time KB build script)"
REQUEST_DELAY_SECONDS = 0.6

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("fetch_sefaria")

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def _get(url, params=None):
    resp = session.get(url, params=params, timeout=20)
    resp.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)
    return resp.json()


_TAG_RE = re.compile(r"<[^>]+>")
_FOOTNOTE_RE = re.compile(r"\s*\n\s*")


def _clean_html(text):
    """Sefaria text/commentary HTML -> plain text (per spec: נקה את הטקסט שנמשך מ-HTML markup)."""
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    text = _FOOTNOTE_RE.sub(" ", text)
    return text.strip()


def _flatten_text(value):
    """Sefaria text/commentary fields can be a string, or a (possibly nested) list of strings."""
    if value is None:
        return ""
    if isinstance(value, str):
        return _clean_html(value)
    if isinstance(value, list):
        return " ".join(_flatten_text(v) for v in value if _flatten_text(v))
    return _clean_html(str(value))


def slugify(name):
    text = unicodedata.normalize("NFKD", name)
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", text)


def resolve_parasha_he_title(parasha_name):
    """שם פרשה -> כותרת עברית, דרך ה-topic 'parashat-<slug>' (קונבנציה אחידה בכל 54 הפרשות ב-Sefaria)."""
    slug = slugify(parasha_name)
    try:
        topic = _get(f"{API_BASE}/topics/parashat-{slug}")
        he_title = (topic.get("primaryTitle") or {}).get("he")
        if he_title:
            return he_title
    except Exception as exc:
        log.warning("לא הצלחתי לפענח כותרת עברית לפרשה '%s': %s — משתמש בשם שהוזן", parasha_name, exc)
    return parasha_name


def resolve_parasha_range(parasha_name):
    """שם פרשה (אנגלית/עברית) -> (book, start_chapter, start_verse, end_chapter, end_verse, he_title)."""
    data = _get(f"{API_BASE}/name/{parasha_name}")
    ref = data.get("ref")
    if not ref:
        raise ValueError(f"לא נמצא טווח פסוקים לפרשה '{parasha_name}' (אין שדה 'ref' בתשובת ה-API)")

    he_title = resolve_parasha_he_title(parasha_name)

    # ref tref ref כללי, למשל: "Numbers 22:2-25:9"
    match = re.match(r"^([1-3]?\s?[A-Za-z]+)\s+(\d+):(\d+)-(?:(\d+):)?(\d+)$", ref)
    if not match:
        raise ValueError(f"לא הצלחתי לפענח טווח פסוקים מהמחרוזת: '{ref}'")

    book, start_ch, start_v, end_ch, end_v = match.groups()
    start_ch = int(start_ch)
    start_v = int(start_v)
    end_v = int(end_v)
    end_ch = int(end_ch) if end_ch else start_ch

    return book.strip(), start_ch, start_v, end_ch, end_v, he_title


def fetch_chapter_commentary_links(book, chapter):
    """מחזיר dict: {"Book C:V": [link_entry, ...]} לכל פסוקי הפרק, ממיון אחד לכל פרק."""
    tref = f"{book}.{chapter}"
    try:
        links = _get(f"{API_BASE}/links/{tref}", params={"with_text": 1, "category": "Commentary"})
    except Exception as exc:
        log.warning("נכשל שליפת פרשנות לפרק %s: %s — מדלג, ממשיך", tref, exc)
        return {}

    by_verse = {}
    for entry in links:
        anchor = entry.get("anchorRef")
        if not anchor:
            continue
        by_verse.setdefault(anchor, []).append(entry)
    return by_verse


def build_commentary_list(link_entries):
    commentaries = []
    for entry in link_entries:
        try:
            commentator_name = (entry.get("collectiveTitle") or {}).get("he") or entry.get("collectiveTitle")
            commentary_text = _flatten_text(entry.get("he"))
            if not commentator_name or not commentary_text:
                continue
            ref = entry.get("ref", "")
            source_url = f"https://www.sefaria.org/{ref.replace(' ', '_')}"
            commentaries.append({
                "commentator_name": commentator_name,
                "commentary_text": commentary_text,
                "source_url": source_url,
            })
        except Exception as exc:
            log.warning("נכשל עיבוד פירוש בודד (%s): %s — מדלג, ממשיך", entry.get("ref"), exc)
    return commentaries


def fetch_verse(book, chapter, verse):
    tref = f"{book}.{chapter}.{verse}"
    data = _get(f"{API_BASE}/texts/{tref}", params={"context": 0, "commentary": 0})
    verse_text_hebrew = _flatten_text(data.get("he"))
    ref_he = data.get("heRef", "")
    return verse_text_hebrew, ref_he


def chapter_verse_count(book, chapter):
    """מספר הפסוקים בפרק, ע''י שליפת הפרק כולו פעם אחת (לא מבוסס על קודי שגיאה)."""
    data = _get(f"{API_BASE}/texts/{book}.{chapter}", params={"context": 0, "commentary": 0})
    he = data.get("he") or []
    return len(he)


def fetch_parasha(parasha_name, out_dir):
    book, start_ch, start_v, end_ch, end_v, he_title = resolve_parasha_range(parasha_name)
    log.info("פרשת %s: %s %s:%s - %s:%s", he_title, book, start_ch, start_v, end_ch, end_v)

    slug = slugify(parasha_name)
    parasha_dir = os.path.join(out_dir, slug)
    os.makedirs(parasha_dir, exist_ok=True)

    total_verses = 0
    total_commentaries = 0

    for chapter in range(start_ch, end_ch + 1):
        links_by_verse = fetch_chapter_commentary_links(book, chapter)

        try:
            chapter_len = chapter_verse_count(book, chapter)
        except Exception as exc:
            log.warning("נכשל לזהות את מספר הפסוקים בפרק %s.%s: %s — מדלג על הפרק", book, chapter, exc)
            continue

        first_verse = start_v if chapter == start_ch else 1
        last_verse = end_v if chapter == end_ch else chapter_len
        last_verse = min(last_verse, chapter_len)

        for verse_num in range(first_verse, last_verse + 1):
            try:
                verse_text_hebrew, ref_he = fetch_verse(book, chapter, verse_num)
            except Exception as exc:
                log.warning("נכשל שליפת %s.%s.%s: %s — מדלג, ממשיך", book, chapter, verse_num, exc)
                continue

            if not verse_text_hebrew:
                log.warning("פסוק %s.%s.%s חזר ריק — מדלג", book, chapter, verse_num)
                continue

            anchor_key = f"{book} {chapter}:{verse_num}"
            commentaries = build_commentary_list(links_by_verse.get(anchor_key, []))

            verse_doc = {
                "perasha": he_title,
                "chapter": chapter,
                "verse": verse_num,
                "verse_text_hebrew": verse_text_hebrew,
                "ref_he": ref_he,
                "source_url": f"https://www.sefaria.org/{book}.{chapter}.{verse_num}",
                "commentaries": commentaries,
            }

            out_path = os.path.join(parasha_dir, f"{chapter:02d}_{verse_num:02d}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(verse_doc, f, ensure_ascii=False, indent=2)

            total_verses += 1
            total_commentaries += len(commentaries)

    log.info("הסתיים: %d פסוקים, %d פירושים, נשמר ב-%s", total_verses, total_commentaries, parasha_dir)


def main():
    parser = argparse.ArgumentParser(description="שליפת פרשת שבוע (טקסט + פרשנות) מ-Sefaria API")
    parser.add_argument("--parasha", required=True, help="שם הפרשה, למשל Balak")
    parser.add_argument("--out-dir", default=os.path.join(os.path.dirname(__file__), "..", "data"))
    args = parser.parse_args()

    fetch_parasha(args.parasha, os.path.abspath(args.out_dir))


if __name__ == "__main__":
    main()
