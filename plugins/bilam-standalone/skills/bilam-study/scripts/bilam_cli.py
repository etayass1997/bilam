"""Offline search, exact Torah counting, and DOCX export for Bilam.

All input data is shipped in the plugin. Python 3.8+ standard library only.
Run `python bilam_cli.py --help` for commands.
"""

from __future__ import annotations

import argparse
import collections
import gzip
import heapq
import json
import math
import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape


SKILL = Path(__file__).resolve().parents[1]
SKILLS = SKILL.parent
ASSETS = SKILL / "assets"
TOKEN_RE = re.compile(r"[\w\u0590-\u05ff]+", re.UNICODE)
NIQQUD_RE = re.compile(r"[\u0591-\u05bd\u05bf-\u05c7]")
HEBREW_WORD_RE = re.compile(r"[\u05d0-\u05ea]+")


def catalog():
    with (ASSETS / "catalog.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def normalize_parasha(value, data):
    if not value:
        return None
    value = value.strip()
    if value in data["shards"]:
        return value
    if not value.startswith("פרשת "):
        value = "פרשת " + value
    if value not in data["shards"]:
        raise ValueError("פרשה לא מוכרת. השתמש בפקודת list לקבלת השמות הזמינים.")
    return value


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            yield json.loads(line)


def verse_rows():
    yield from rows(ASSETS / "verses.jsonl.gz")


def source_rows(data, parasha=None):
    parasha_id = data["parashot"].index(parasha) if parasha else None
    for row in verse_rows():
        if parasha_id is None or row[1] == parasha_id:
            yield row
    shard_numbers = [data["shards"][parasha]] if parasha else range(1, 13)
    for number in shard_numbers:
        path = SKILLS / f"bilam-corpus-{number:02d}" / "assets" / "commentaries.jsonl.gz"
        for row in rows(path):
            if parasha_id is None or row[1] == parasha_id:
                yield row


def hebrew_number(value):
    if not isinstance(value, int) or value <= 0 or value >= 1000:
        return str(value or "")
    number = value
    letters = []
    for amount, letter in ((400, "ת"), (300, "ש"), (200, "ר"), (100, "ק"), (90, "צ"), (80, "פ"), (70, "ע"), (60, "ס"), (50, "נ"), (40, "מ"), (30, "ל"), (20, "כ")):
        while number >= amount:
            letters.append(letter)
            number -= amount
    if number == 15:
        letters.extend(("ט", "ו"))
        number = 0
    elif number == 16:
        letters.extend(("ט", "ז"))
        number = 0
    for amount, letter in ((10, "י"), (9, "ט"), (8, "ח"), (7, "ז"), (6, "ו"), (5, "ה"), (4, "ד"), (3, "ג"), (2, "ב"), (1, "א")):
        while number >= amount:
            letters.append(letter)
            number -= amount
    numeral = "".join(letters)
    return numeral + "׳" if len(numeral) == 1 else numeral[:-1] + "״" + numeral[-1]


def source_record(row, data):
    _, parasha_id, chapter, verse, commentator_id, body, url, ref, _ = row
    parasha = data["parashot"][parasha_id]
    commentator = data["commentators"][commentator_id] if commentator_id >= 0 else None
    label = f"{parasha}, פרק {hebrew_number(chapter)}, פסוק {hebrew_number(verse)} — {commentator or 'טקסט התורה'}"
    return {
        "text": body,
        "parasha": parasha,
        "chapter": chapter,
        "verse": verse,
        "source_label": label,
        "ref_he": ref,
        "commentator_name": commentator,
        "source_type": "commentary" if commentator else "torah",
        "source_url": url,
    }


def search(query, parasha=None, limit=6):
    data = catalog()
    parasha = normalize_parasha(parasha, data)
    if not query.strip() or not 1 <= limit <= 20:
        raise ValueError("נדרשים שאילתה ואורך תוצאות בין 1 ל־20.")
    terms = collections.Counter(TOKEN_RE.findall(query.lower()))
    with gzip.open(ASSETS / "document_frequency.json.gz", "rt", encoding="utf-8") as handle:
        df = json.load(handle)
    n = data["documents"]
    idf = {}
    for term in terms:
        frequency = df.get(term, 0)
        if frequency:
            raw = math.log(n - frequency + 0.5) - math.log(frequency + 0.5)
            idf[term] = raw if raw >= 0 else data["epsilon_idf"]
    heap = []
    average_length = data["average_document_length"]
    for row in source_rows(data, parasha):
        tokens = TOKEN_RE.findall(row[5].lower())
        counts = collections.Counter(token for token in tokens if token in terms)
        if not counts:
            continue
        length = row[8]
        denominator_base = 1.5 * (0.25 + 0.75 * length / average_length)
        score = sum(
            idf.get(term, 0) * repetition * (frequency * 2.5) / (frequency + denominator_base)
            for term, repetition in terms.items()
            if (frequency := counts.get(term, 0))
        )
        if score <= 0:
            continue
        candidate = (score, -row[0], row)
        if len(heap) < limit:
            heapq.heappush(heap, candidate)
        elif candidate > heap[0]:
            heapq.heapreplace(heap, candidate)
    sources = [source_record(item[2], data) for item in sorted(heap, reverse=True)]
    return {"query": query, "parasha": parasha, "count": len(sources), "sources": sources}


def count_word(word, match_type="exact_word", parasha=None, max_matches=25):
    data = catalog()
    parasha = normalize_parasha(parasha, data)
    if match_type not in ("exact_word", "substring"):
        raise ValueError("match_type חייב להיות exact_word או substring.")
    target = NIQQUD_RE.sub("", word).strip()
    if not target:
        raise ValueError("לא סופקה מילה לחיפוש.")
    parasha_id = data["parashot"].index(parasha) if parasha else None
    matches = []
    total = 0
    verses_count = 0
    for row in verse_rows():
        if parasha_id is not None and row[1] != parasha_id:
            continue
        tokens = HEBREW_WORD_RE.findall(NIQQUD_RE.sub("", row[5]))
        count = sum(target in token if match_type == "substring" else target == token for token in tokens)
        if count:
            total += count
            verses_count += 1
            matches.append({
                "ref_he": row[7], "parasha": data["parashot"][row[1]],
                "chapter": row[2], "verse": row[3], "count": count,
                "verse_text": row[5],
            })
    # Same ordering as TextStats._verses: chapter/verse, stable on ties.
    matches.sort(key=lambda item: (item["chapter"] or 0, item["verse"] or 0))
    return {
        "word": word, "match_type": match_type, "parasha": parasha,
        "total_occurrences": total, "verses_count": verses_count,
        "matches": matches[:max_matches], "matches_truncated": verses_count > max_matches,
    }


def parasha_stats(parasha):
    data = catalog()
    parasha = normalize_parasha(parasha, data)
    if not parasha:
        raise ValueError("נדרש שם פרשה.")
    parasha_id = data["parashot"].index(parasha)
    verses = [row for row in verse_rows() if row[1] == parasha_id]
    return {
        "parasha": parasha,
        "total_verses": len(verses),
        "total_words": sum(len(HEBREW_WORD_RE.findall(NIQQUD_RE.sub("", row[5]))) for row in verses),
        "chapters": sorted({row[2] for row in verses if row[2] is not None}),
    }


def write_docx(path, query, sources):
    """Create a basic RTL Word file without an external Python dependency."""
    paragraphs = ["בלעם — מקורות לפרשת השבוע", f"שאלה: {query}"]
    for source in sources:
        paragraphs.extend((source["source_label"], source["text"], source.get("source_url") or ""))
    document = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>',
    ]
    for paragraph in paragraphs:
        if paragraph:
            document.append(f'<w:p><w:pPr><w:bidi/></w:pPr><w:r><w:rPr><w:rtl/></w:rPr><w:t xml:space="preserve">{escape(paragraph)}</w:t></w:r></w:p>')
    document.append("<w:sectPr/></w:body></w:document>")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        archive.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        archive.writestr("word/document.xml", "".join(document))
    return str(path.resolve())


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bilam, full corpus without a server or API key")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List Torah portions and corpus size")
    search_parser = sub.add_parser("search", help="BM25 search over all sources")
    search_parser.add_argument("query")
    search_parser.add_argument("--parasha")
    search_parser.add_argument("--limit", type=int, default=6)
    count_parser = sub.add_parser("count", help="Exact word count in Torah verses")
    count_parser.add_argument("word")
    count_parser.add_argument("--parasha")
    count_parser.add_argument("--match-type", choices=("exact_word", "substring"), default="exact_word")
    stats_parser = sub.add_parser("stats", help="Exact portion statistics")
    stats_parser.add_argument("parasha")
    docx_parser = sub.add_parser("docx", help="Export retrieved sources to a Word document")
    docx_parser.add_argument("query")
    docx_parser.add_argument("--parasha")
    docx_parser.add_argument("--limit", type=int, default=6)
    docx_parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            data = catalog()
            result = {"parashot": data["parashot"], "documents": data["documents"], "torah_verses": data["torah_verses"], "commentaries": data["commentaries"]}
        elif args.command == "search":
            result = search(args.query, args.parasha, args.limit)
        elif args.command == "count":
            result = count_word(args.word, args.match_type, args.parasha)
        elif args.command == "stats":
            result = parasha_stats(args.parasha)
        else:
            found = search(args.query, args.parasha, args.limit)
            result = {"path": write_docx(args.output, args.query, found["sources"]), "sources": found["count"]}
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
