import io
import os

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt
from flask import Flask, jsonify, request, send_file, send_from_directory

from rag_engine import RAGEngine
from text_stats import TextStats

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
rag_engine = RAGEngine()
text_stats = TextStats(rag_engine)
PARASHOT = tuple(rag_engine.parashot())
PARASHOT_SET = set(PARASHOT)


def _hebrew_number(value):
    """Format a positive integer as conventional Hebrew numerals."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return str(value or "")

    if number <= 0 or number >= 1000:
        return str(number)

    letters = []
    for amount, letter in (
        (400, "ת"), (300, "ש"), (200, "ר"), (100, "ק"),
        (90, "צ"), (80, "פ"), (70, "ע"), (60, "ס"), (50, "נ"),
        (40, "מ"), (30, "ל"), (20, "כ"),
    ):
        while number >= amount:
            letters.append(letter)
            number -= amount

    # The traditional forms avoid spelling the Divine name for 15 and 16.
    if number == 15:
        letters.extend(("ט", "ו"))
        number = 0
    elif number == 16:
        letters.extend(("ט", "ז"))
        number = 0

    for amount, letter in (
        (10, "י"), (9, "ט"), (8, "ח"), (7, "ז"), (6, "ו"),
        (5, "ה"), (4, "ד"), (3, "ג"), (2, "ב"), (1, "א"),
    ):
        while number >= amount:
            letters.append(letter)
            number -= amount

    numeral = "".join(letters)
    if len(numeral) == 1:
        return f"{numeral}׳"
    return f"{numeral[:-1]}״{numeral[-1]}"


def _format_source_label(meta, include_source=True):
    parasha = meta.get("parasha") or "פרשה לא ידועה"
    if not parasha.startswith("פרשת "):
        parasha = f"פרשת {parasha}"
    chapter = meta.get("chapter")
    verse = meta.get("verse")
    commentator = meta.get("commentator_name")
    label = f"{parasha}, פרק {_hebrew_number(chapter)}, פסוק {_hebrew_number(verse)}"
    if not include_source:
        return label
    return f"{label} — {commentator or 'טקסט התורה'}"


def search_sources(query, n=6, parasha=None):
    results = rag_engine.search(query, n=n, parashot=[parasha] if parasha else None)
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    sources = []
    for text, meta in zip(documents, metadatas):
        label = _format_source_label(meta)
        sources.append({
            "text": text,
            "parasha": meta.get("parasha"),
            "chapter": meta.get("chapter"),
            "verse": meta.get("verse"),
            "source_label": label,
            "ref_he": meta.get("ref_he"),
            "commentator_name": meta.get("commentator_name"),
            "source_type": meta.get("source_type"),
            "source_url": meta.get("source_url"),
        })
    return sources


def selected_parasha(raw):
    if not raw:
        return None
    value = raw.strip()
    if not value.startswith("פרשת "):
        value = f"פרשת {value}"
    return value if value in PARASHOT_SET else None


def last_user_message(messages):
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, list):
                return " ".join(b.get("text", "") for b in content if isinstance(b, dict))
            return content
    return ""


@app.route("/", methods=["GET"])
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "doc_count": rag_engine.count()})


@app.route("/parashot", methods=["GET"])
def parashot():
    return jsonify({"parashot": PARASHOT})


@app.route("/config", methods=["GET"])
def config():
    return jsonify({"plugin_url": os.environ.get("PLUGIN_URL", "")})


@app.route("/api/search", methods=["GET"])
def api_search():
    query = request.args.get("query", "").strip()
    raw_parasha = request.args.get("parasha", "").strip()
    if not query or len(query) > 500:
        return jsonify({"error": "נדרשת שאילתה באורך 1 עד 500 תווים"}), 400
    parasha = selected_parasha(raw_parasha)
    if raw_parasha and not parasha:
        return jsonify({"error": "פרשה לא מוכרת; השתמשו ב-/api/parashot"}), 400
    try:
        limit = int(request.args.get("limit", 6))
    except ValueError:
        return jsonify({"error": "limit חייב להיות מספר שלם"}), 400
    if not 1 <= limit <= 10:
        return jsonify({"error": "limit חייב להיות בין 1 ל-10"}), 400
    sources = search_sources(query, n=limit, parasha=parasha)
    return jsonify({"query": query, "parasha": parasha, "sources": sources, "count": len(sources)})


@app.route("/api/parashot", methods=["GET"])
def api_parashot():
    return jsonify({"parashot": PARASHOT})


@app.route("/api/count-word", methods=["GET"])
def api_count_word():
    word = request.args.get("word", "").strip()
    raw_parasha = request.args.get("parasha", "").strip()
    match_type = request.args.get("match_type", "exact_word")
    if not word or len(word) > 50:
        return jsonify({"error": "נדרשת מילה באורך 1 עד 50 תווים"}), 400
    if match_type not in ("exact_word", "substring"):
        return jsonify({"error": "match_type לא מוכר"}), 400
    parasha = selected_parasha(raw_parasha)
    if raw_parasha and not parasha:
        return jsonify({"error": "פרשה לא מוכרת; השתמשו ב-/api/parashot"}), 400
    return jsonify(text_stats.count_word(word, match_type, parasha=parasha))


@app.route("/api/parasha-stats", methods=["GET"])
def api_parasha_stats():
    raw_parasha = request.args.get("parasha", "").strip()
    parasha = selected_parasha(raw_parasha)
    if not parasha:
        return jsonify({"error": "נדרשת פרשה מוכרת; השתמשו ב-/api/parashot"}), 400
    return jsonify(text_stats.get_parasha_stats(parasha))


@app.route("/chat", methods=["POST"])
def retired_chat():
    return jsonify({"error": "השיחה עברה ל-ChatGPT; שרת זה מספק מקורות ונתונים בלבד"}), 410


def _set_rtl(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_pr = paragraph._p.get_or_add_pPr()
    bidi = p_pr.makeelement(qn("w:bidi"), {})
    p_pr.append(bidi)


def build_docx(question, context_groups):
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(12)

    title = doc.add_heading(question, level=1)
    _set_rtl(title)

    for group in context_groups:
        verse_p = doc.add_paragraph()
        verse_run = verse_p.add_run(f"{group['ref_he']}: {group['verse_text_hebrew']}")
        verse_run.bold = True
        _set_rtl(verse_p)

        for commentary in group["commentaries"]:
            c_p = doc.add_paragraph()
            c_run = c_p.add_run(f"{commentary['commentator_name']}: {commentary['text']}")
            _set_rtl(c_p)
            c_p.paragraph_format.left_indent = Pt(18)

        doc.add_paragraph()

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


@app.route("/generate-docx", methods=["POST", "OPTIONS"])
def generate_docx():
    if request.method == "OPTIONS":
        return "", 204

    data = request.json or {}
    messages = data.get("messages", [])
    if not messages:
        return jsonify({"error": "לא התקבלה שאלה"}), 400

    query = last_user_message(messages)
    results = rag_engine.search(query, n=10)
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    groups = {}
    for text, meta in zip(documents, metadatas):
        key = (meta.get("parasha"), meta.get("chapter"), meta.get("verse"))
        if key not in groups:
            groups[key] = {
                "ref_he": _format_source_label(meta, include_source=False),
                "verse_text_hebrew": meta.get("verse_text_hebrew"),
                "commentaries": [],
            }
        if meta.get("source_type") == "commentary":
            groups[key]["commentaries"].append({
                "commentator_name": meta.get("commentator_name"),
                "text": text,
            })

    ordered_groups = [groups[k] for k in sorted(groups.keys())]

    if not ordered_groups:
        return jsonify({"error": "לא נמצאו מקורות רלוונטיים במאגר עבור שאלה זו"}), 404

    buffer = build_docx(query, ordered_groups)
    return send_file(
        buffer,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name="bilam.docx",
    )


if __name__ == "__main__":
    raise SystemExit("Run the combined service with: uvicorn server:app --host 127.0.0.1 --port 5007")
