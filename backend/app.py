import io
import os

import anthropic
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

from rag_engine import RAGEngine

app = Flask(__name__)
CORS(app, origins="*")

rag_engine = RAGEngine()

SYSTEM_PROMPT = """אתה בלעם — סוכן ידע לפרשת שבוע, מבוסס על טקסט התורה והפרשנים הקלאסיים.

חוקי יסוד:
- ענה רק על בסיס המידע שמופיע ב"מקורות" שסופקו לך כאן בהודעה הזו. אל תשתמש בידע כללי שלך על הפרשה, גם אם אתה "זוכר" אותו.
- בכל תשובה ציין במפורש מאיזה פסוק (פרק:פסוק) ומאיזה מפרש המידע הגיע, בפורמט עקבי: (פרק X פסוק Y — שם המפרש), ולפסוקי תורה עצמם: (פרק X פסוק Y — טקסט התורה).
- אם המקורות שסופקו לא מכילים תשובה לשאלה — אמור זאת בבירור ("לא מצאתי מידע על כך במאגר"), ואל תמציא תשובה.
- עברית בלבד. תמציתי וממוקד.

מקורות שנמצאו לשאלה הנוכחית:
{context}"""


def _format_source_label(meta):
    chapter = meta.get("chapter")
    verse = meta.get("verse")
    commentator = meta.get("commentator_name")
    if commentator:
        return f"פרק {chapter} פסוק {verse} — {commentator}"
    return f"פרק {chapter} פסוק {verse} — טקסט התורה"


def retrieve_context(query, n=6):
    results = rag_engine.search(query, n=n)
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    context_lines = []
    sources = []
    for text, meta in zip(documents, metadatas):
        label = _format_source_label(meta)
        context_lines.append(f"[{label}]\n{text}")
        sources.append({
            "chapter": meta.get("chapter"),
            "verse": meta.get("verse"),
            "ref_he": meta.get("ref_he"),
            "commentator_name": meta.get("commentator_name"),
            "source_type": meta.get("source_type"),
            "source_url": meta.get("source_url"),
        })
    return "\n\n".join(context_lines), sources


def last_user_message(messages):
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, list):
                return " ".join(b.get("text", "") for b in content if isinstance(b, dict))
            return content
    return ""


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "doc_count": rag_engine.count()})


@app.route("/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        return "", 204

    data = request.json or {}
    messages = data.get("messages", [])
    api_key = data.get("api_key")

    if not api_key:
        return jsonify({"error": "חובה להזין מפתח Anthropic API"}), 400
    if not messages:
        return jsonify({"error": "לא התקבלה שאלה"}), 400

    query = last_user_message(messages)
    context, sources = retrieve_context(query)

    if not context:
        context = "(לא נמצאו מקורות רלוונטיים במאגר עבור שאלה זו)"

    system = SYSTEM_PROMPT.format(context=context)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=system,
            messages=messages,
        )
        text_blocks = [b.text for b in response.content if hasattr(b, "text")]
        reply = text_blocks[0] if text_blocks else ""
    except anthropic.AuthenticationError:
        return jsonify({"error": "מפתח ה-API שגוי או לא תקף"}), 401
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        api_key = None  # never retained past this request

    return jsonify({"reply": reply, "sources": sources})


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
        key = (meta.get("chapter"), meta.get("verse"))
        if key not in groups:
            groups[key] = {
                "ref_he": meta.get("ref_he"),
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
    port = int(os.environ.get("PORT", 5005))
    app.run(host="0.0.0.0", port=port)
