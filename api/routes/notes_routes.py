"""Student-owned smart notes and diagram endpoints."""
import json
from functools import wraps
from flask import Blueprint, jsonify, request, session
from api.db import execute, query_all, query_one
from api.gemini_service import analyze_notes_and_generate_visuals, clean_textbook_text, extract_text_from_page_images, generate_visuals

notes_bp = Blueprint("notes", __name__, url_prefix="/api/notes")

def signed_in(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("student_id"):
            return jsonify(error="Please sign in to manage your notes."), 401
        return view(*args, **kwargs)
    return wrapped

def _note(row):
    if not row:
        return None
    item = dict(row)
    for key in ("key_points", "definitions"):
        value = item.get(key)
        if isinstance(value, str):
            try: value = json.loads(value)
            except (ValueError, TypeError): item[key] = []
        if not isinstance(value, list):
            item[key] = []
        else:
            item[key] = value
    return item

@notes_bp.route("", methods=["GET"], strict_slashes=False)
@notes_bp.route("/", methods=["GET"], strict_slashes=False)
@signed_in
def list_notes():
    rows = query_all("SELECT id,title,subject,summary,key_points,definitions,created_at FROM notes WHERE student_id=%s ORDER BY created_at DESC,id DESC", (session["student_id"],))
    return jsonify(notes=[_note(row) for row in rows])

@notes_bp.post("/generate")
@signed_in
def create_note():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    subject = str(data.get("subject", "")).strip()
    content = clean_textbook_text(data.get("raw_content", ""))
    page_images = data.get("page_images") if isinstance(data.get("page_images"), list) else []
    if not title or len(title) > 180:
        return jsonify(error="Add a title of 1–180 characters."), 400
    if len(subject) > 100:
        return jsonify(error="Subject must be 100 characters or fewer."), 400
    if len(content) < 30 and not page_images:
        return jsonify(error="Add at least 30 characters of notes to analyze."), 400
    if len(content) > 100000:
        return jsonify(error="Notes are too long. Please keep them under 100,000 characters."), 413
    if page_images:
        ocr_text = extract_text_from_page_images(page_images[:15])
        if len(ocr_text) >= 30:
            content = ocr_text
    if len(content) < 30:
        return jsonify(error="Could not read enough textbook text. Please paste notes or upload a clearer PDF."), 422
    if len(content) > 100000:
        content = content[:100000]
    generated = analyze_notes_and_generate_visuals(title, subject, content)
    row = execute("""INSERT INTO notes (student_id,title,subject,raw_content,summary,key_points,definitions,flowchart_mermaid,mindmap_mermaid)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id,student_id,title,subject,raw_content,summary,key_points,definitions,flowchart_mermaid,mindmap_mermaid,created_at""",
                  (session["student_id"], title, subject or None, content, generated["summary"],
                   json.dumps(generated["key_points"]), json.dumps(generated["definitions"]),
                   generated["flowchart_mermaid"], generated["mindmap_mermaid"]))
    return jsonify(note=_note(row)), 201

@notes_bp.get("/<int:note_id>")
@signed_in
def get_note(note_id):
    row = query_one("SELECT id,student_id,title,subject,raw_content,summary,key_points,definitions,flowchart_mermaid,mindmap_mermaid,created_at FROM notes WHERE id=%s AND student_id=%s", (note_id, session["student_id"]))
    if not row: return jsonify(error="Note not found."), 404
    return jsonify(note=_note(row))

@notes_bp.post("/<int:note_id>/regenerate-diagrams")
@signed_in
def regenerate_diagrams(note_id):
    row = query_one("SELECT id,title,subject,raw_content FROM notes WHERE id=%s AND student_id=%s", (note_id, session["student_id"]))
    if not row: return jsonify(error="Note not found."), 404
    diagrams = generate_visuals(row["title"], row["subject"], row["raw_content"])
    updated = execute("UPDATE notes SET flowchart_mermaid=%s,mindmap_mermaid=%s WHERE id=%s AND student_id=%s RETURNING id,flowchart_mermaid,mindmap_mermaid",
                      (diagrams["flowchart_mermaid"], diagrams["mindmap_mermaid"], note_id, session["student_id"]))
    return jsonify(note=dict(updated))

@notes_bp.delete("/<int:note_id>")
@signed_in
def delete_note(note_id):
    row = query_one("DELETE FROM notes WHERE id=%s AND student_id=%s RETURNING id", (note_id, session["student_id"]))
    if not row: return jsonify(error="Note not found."), 404
    return jsonify(ok=True, id=note_id)
