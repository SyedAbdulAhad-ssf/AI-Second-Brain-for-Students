"""Grounded note chat and personalized revision-plan routes."""
import json
import logging
from datetime import date
from functools import wraps
from flask import Blueprint, jsonify, request, session
from api.db import execute, query_all, query_one
from api.gemini_service import answer_from_notes_rag, generate_smart_revision_plan

rag_bp = Blueprint("rag", __name__, url_prefix="/api/rag")
log = logging.getLogger(__name__)

def _chat_fallback(note, question):
    points = note.get("key_points") if isinstance(note.get("key_points"), list) else []
    definitions = note.get("definitions") if isinstance(note.get("definitions"), list) else []
    summary = str(note.get("summary") or "").strip()
    raw_content = str(note.get("raw_content") or "").strip()
    excerpt = "\n".join(f"- {str(point)[:700]}" for point in points[:5])
    if not excerpt:
        excerpt = summary or raw_content[:2500] or "This note does not contain readable study text yet."
    definition_text = "\n".join(
        f"- {str(item.get('term') or 'Key idea')}: {str(item.get('definition') or '')[:500]}"
        for item in definitions[:3] if isinstance(item, dict)
    )
    answer = f"Here is a note-based explanation of ‘{question[:180]}’:\n{excerpt}"
    if definition_text:
        answer += f"\n\nKey definitions:\n{definition_text}"
    if summary and excerpt != summary:
        answer += f"\n\nChapter summary: {summary[:1200]}"
    return {
        "answer": answer[:5000],
        "source_reference": f"{note.get('subject') or 'Study notes'} — {note.get('title') or 'Your note'} | Summary and key points",
        "suggested_followups": ["Explain one key definition", "Show an example from this note", "Quiz me on this chapter"],
    }

def signed_in(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("student_id"): return jsonify(error="Please sign in to continue."), 401
        return view(*args, **kwargs)
    return wrapped

def decode(row, *keys):
    item = dict(row) if row else None
    if item:
        for key in keys:
            if isinstance(item.get(key), str):
                try: item[key] = json.loads(item[key])
                except (ValueError, TypeError): item[key] = []
    return item

def owned_note(note_id):
    row = query_one("SELECT id,title,subject,raw_content,summary,key_points,definitions FROM notes WHERE id=%s AND student_id=%s", (note_id, session["student_id"]))
    return decode(row, "key_points", "definitions")

@rag_bp.get("/chat/<int:note_id>")
@signed_in
def get_chat(note_id):
    note = owned_note(note_id)
    if not note: return jsonify(error="Note not found."), 404
    history = query_all("SELECT id,role,message,source_reference,created_at FROM chat_messages WHERE student_id=%s AND note_id=%s ORDER BY created_at,id", (session["student_id"], note_id))
    return jsonify(note={key: note[key] for key in ("id", "title", "subject")}, messages=[dict(row) for row in history], sample_questions=["Explain the main concepts of this chapter in simple words", "List all important formulas and definitions for exam", "How do we predict the direction and extent of reaction using Kc and Qc?", "Give me 5 important short questions with answers from these notes"])

@rag_bp.post("/chat")
@signed_in
def post_chat():
    data = request.get_json(silent=True) or {}
    try: note_id = int(data.get("note_id"))
    except (TypeError, ValueError): return jsonify(error="Choose a note before asking a question."), 400
    question = str(data.get("question", "")).strip()
    if not 2 <= len(question) <= 1500: return jsonify(error="Ask a question between 2 and 1,500 characters."), 400
    fallback_used = False
    try:
        note = owned_note(note_id)
        if not note: return jsonify(error="Note not found."), 404
        history = [dict(row) for row in query_all("SELECT role,message FROM chat_messages WHERE student_id=%s AND note_id=%s ORDER BY created_at DESC,id DESC LIMIT 10", (session["student_id"], note_id))]
        reply = answer_from_notes_rag(note, question, list(reversed(history)))
    except Exception:
        log.exception("Tutor chat failed; returning a note-based fallback")
        fallback_used = True
        reply = _chat_fallback(locals().get("note") or {}, question)
    try:
        user = execute("INSERT INTO chat_messages (student_id,note_id,role,message) VALUES (%s,%s,%s,%s) RETURNING id,role,message,source_reference,created_at", (session["student_id"], note_id, "user", question))
        assistant = execute("INSERT INTO chat_messages (student_id,note_id,role,message,source_reference) VALUES (%s,%s,%s,%s,%s) RETURNING id,role,message,source_reference,created_at", (session["student_id"], note_id, "assistant", reply["answer"], reply["source_reference"]))
        return jsonify(user_message=dict(user), assistant_message=dict(assistant), suggested_followups=reply["suggested_followups"]), (200 if fallback_used else 201)
    except Exception:
        log.exception("Tutor chat persistence failed; returning the generated reply without history")
        return jsonify(user_message={"role": "user", "message": question},
                       assistant_message={"role": "assistant", "message": reply["answer"], "source_reference": reply["source_reference"]},
                       suggested_followups=reply["suggested_followups"]), 200

@rag_bp.delete("/chat/<int:note_id>")
@signed_in
def clear_chat(note_id):
    if not owned_note(note_id): return jsonify(error="Note not found."), 404
    execute("DELETE FROM chat_messages WHERE student_id=%s AND note_id=%s", (session["student_id"], note_id))
    return jsonify(ok=True)

def plan_payload(plan):
    item = decode(plan, "schedule")
    if not item: return None
    tasks = [task for day in item["schedule"] for task in day.get("tasks", [])]
    item["completion_percentage"] = round((sum(1 for task in tasks if task.get("done")) / len(tasks)) * 100) if tasks else 0
    if item["schedule"]:
        item["exam_title"] = item["schedule"][0].get("exam_title", "Matric Exam")
        item["priority_focus"] = item["schedule"][0].get("priority_focus", "saved_and_weak")
    return item

@rag_bp.get("/revision")
@signed_in
def get_revision():
    plan = query_one("SELECT id,student_id,exam_date,daily_hours,schedule,created_at FROM revision_plans WHERE student_id=%s ORDER BY created_at DESC,id DESC LIMIT 1", (session["student_id"],))
    gaps = query_one("SELECT COUNT(*) AS count FROM knowledge_gaps WHERE student_id=%s AND status='needs_practice'", (session["student_id"],))
    notes = query_one("SELECT COUNT(*) AS count FROM notes WHERE student_id=%s", (session["student_id"],))
    return jsonify(plan=plan_payload(plan), active_knowledge_gaps=gaps["count"], notes_count=notes["count"])

@rag_bp.post("/revision/generate")
@signed_in
def generate_revision():
    data = request.get_json(silent=True) or {}; exam_date = str(data.get("exam_date", "")); daily_hours = data.get("daily_hours", 2)
    exam_title = str(data.get("exam_title", "Matric Exam")).strip()[:120] or "Matric Exam"
    priority_focus = str(data.get("priority_focus", "saved_and_weak"))
    if priority_focus not in ("saved_and_weak", "weak_concepts", "saved_notes"): priority_focus = "saved_and_weak"
    try: date.fromisoformat(exam_date); daily_hours = max(1, min(8, int(daily_hours)))
    except (ValueError, TypeError): return jsonify(error="Provide a valid exam date and 1–8 daily hours."), 400
    notes = [decode(row, "key_points", "definitions") for row in query_all("SELECT id,title,subject,raw_content,summary,key_points,definitions FROM notes WHERE student_id=%s ORDER BY created_at DESC", (session["student_id"],))]
    if not notes: return jsonify(error="Create at least one smart note before generating a revision plan."), 400
    gaps = [dict(row) for row in query_all("SELECT note_id,weak_topic,status FROM knowledge_gaps WHERE student_id=%s", (session["student_id"],))]
    attempts = [dict(row) for row in query_all("SELECT q.note_id,a.score,a.total_questions FROM quiz_attempts a JOIN quizzes q ON q.id=a.quiz_id WHERE a.student_id=%s ORDER BY a.attempted_at DESC", (session["student_id"],))]
    generated = generate_smart_revision_plan(exam_date, daily_hours, notes, gaps, attempts, exam_title, priority_focus)
    plan = execute("INSERT INTO revision_plans (student_id,exam_date,daily_hours,schedule) VALUES (%s,%s,%s,%s) RETURNING id,student_id,exam_date,daily_hours,schedule,created_at", (session["student_id"], exam_date, daily_hours, json.dumps(generated["schedule"])))
    result = plan_payload(plan); result["summary_advice"] = generated["summary_advice"]
    return jsonify(plan=result), 201

@rag_bp.post("/revision/<int:plan_id>/toggle-task")
@signed_in
def toggle_task(plan_id):
    data = request.get_json(silent=True) or {}; day_number, task_id = data.get("day_number"), str(data.get("task_id", "")); done = bool(data.get("done"))
    plan = query_one("SELECT id,student_id,exam_date,daily_hours,schedule,created_at FROM revision_plans WHERE id=%s AND student_id=%s", (plan_id, session["student_id"]))
    if not plan: return jsonify(error="Revision plan not found."), 404
    plan = decode(plan, "schedule"); found = False
    for day in plan["schedule"]:
        if day.get("day_number") == day_number:
            for task in day.get("tasks", []):
                if task.get("id") == task_id: task["done"] = done; found = True
    if not found: return jsonify(error="Revision task not found."), 404
    updated = execute("UPDATE revision_plans SET schedule=%s WHERE id=%s AND student_id=%s RETURNING id,student_id,exam_date,daily_hours,schedule,created_at", (json.dumps(plan["schedule"]), plan_id, session["student_id"]))
    return jsonify(plan=plan_payload(updated))
