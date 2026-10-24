"""Student-scoped assessment and knowledge-gap routes."""
import json
import re
from functools import wraps
from flask import Blueprint, jsonify, request, session
from api.db import execute, query_all, query_one
from api.gemini_service import detect_knowledge_gaps, generate_quiz_and_flashcards

quiz_bp = Blueprint("quiz", __name__, url_prefix="/api/quizzes")

def signed_in(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("student_id"):
            return jsonify(error="Please sign in to use assessments."), 401
        return view(*args, **kwargs)
    return wrapped

def decode(row, *keys):
    item = dict(row) if row else None
    if item:
        for key in keys:
            if isinstance(item.get(key), str):
                try: item[key] = json.loads(item[key])
                except (TypeError, ValueError): item[key] = []
    return item

def note_for_student(note_id):
    return query_one("SELECT id,title,subject,raw_content,summary,key_points,definitions FROM notes WHERE id=%s AND student_id=%s", (note_id, session["student_id"]))

@quiz_bp.post("/generate")
@signed_in
def generate_quiz():
    data = request.get_json(silent=True) or {}
    try: note_id = int(data.get("note_id"))
    except (ValueError, TypeError): return jsonify(error="Choose a saved note first."), 400
    note = note_for_student(note_id)
    if not note: return jsonify(error="Note not found."), 404
    note = decode(note, "key_points", "definitions")
    difficulty = str(data.get("difficulty", "medium"))
    key_points = note.get("key_points") if isinstance(note.get("key_points"), list) else []
    definitions = note.get("definitions") if isinstance(note.get("definitions"), list) else []
    try:
        assessment = generate_quiz_and_flashcards(
            str(note.get("title") or "Study note"), str(note.get("subject") or ""),
            str(note.get("raw_content") or ""), str(note.get("summary") or ""),
            key_points, definitions, difficulty
        )
    except Exception:
        # The service has its own Gemini fallback; this also protects the route
        # from unexpected source-data or response-normalization errors.
        from api.gemini_service import _assessment_fallback
        assessment = _assessment_fallback(
            str(note.get("title") or "Study note"), str(note.get("subject") or ""),
            str(note.get("raw_content") or ""), str(note.get("summary") or ""),
            key_points, definitions, difficulty
        )
    quiz = execute("INSERT INTO quizzes (note_id,student_id,questions,flashcards) VALUES (%s,%s,%s,%s) RETURNING id,note_id,student_id,questions,flashcards,created_at", (note_id, session["student_id"], json.dumps(assessment["questions"]), json.dumps(assessment["flashcards"])))
    return jsonify(quiz=decode(quiz, "questions", "flashcards")), 200

@quiz_bp.route("", methods=["GET"], strict_slashes=False)
@quiz_bp.route("/", methods=["GET"], strict_slashes=False)
@signed_in
def list_quizzes():
    rows = query_all("SELECT q.id,q.note_id,q.created_at,n.title AS note_title,n.subject,(SELECT score FROM quiz_attempts a WHERE a.quiz_id=q.id AND a.student_id=q.student_id ORDER BY a.attempted_at DESC,a.id DESC LIMIT 1) AS latest_score,(SELECT total_questions FROM quiz_attempts a WHERE a.quiz_id=q.id AND a.student_id=q.student_id ORDER BY a.attempted_at DESC,a.id DESC LIMIT 1) AS latest_total FROM quizzes q JOIN notes n ON n.id=q.note_id WHERE q.student_id=%s ORDER BY q.created_at DESC,q.id DESC", (session["student_id"],))
    return jsonify(quizzes=[dict(row) for row in rows])

@quiz_bp.get("/note/<int:note_id>")
@signed_in
def quiz_for_note(note_id):
    if not note_for_student(note_id): return jsonify(error="Note not found."), 404
    quiz = query_one("SELECT id,note_id,student_id,questions,flashcards,created_at FROM quizzes WHERE note_id=%s AND student_id=%s ORDER BY created_at DESC,id DESC LIMIT 1", (note_id, session["student_id"]))
    if not quiz: return jsonify(quiz=None, attempts=[])
    quiz = decode(quiz, "questions", "flashcards")
    attempts = query_all("SELECT id,score,total_questions,wrong_answers,attempted_at FROM quiz_attempts WHERE quiz_id=%s AND student_id=%s ORDER BY attempted_at DESC,id DESC", (quiz["id"], session["student_id"]))
    return jsonify(quiz=quiz, attempts=[decode(row, "wrong_answers") for row in attempts])

def grade_question(question, answer):
    answer_text = str(answer or "").strip()
    if question.get("type") == "mcq": return answer_text.lower() == str(question.get("correct_answer", "")).strip().lower(), answer_text
    words = set(re.findall(r"[a-z0-9]+", answer_text.lower()))
    keywords = [str(value).lower() for value in question.get("keywords", []) if str(value).strip()]
    return bool(words and keywords and sum(1 for word in keywords if word in words) >= max(1, min(2, len(keywords)))), answer_text

@quiz_bp.post("/<int:quiz_id>/submit")
@signed_in
def submit_quiz(quiz_id):
    quiz = query_one("SELECT q.id,q.note_id,q.questions,n.title,n.subject,n.raw_content FROM quizzes q JOIN notes n ON n.id=q.note_id WHERE q.id=%s AND q.student_id=%s", (quiz_id, session["student_id"]))
    if not quiz: return jsonify(error="Quiz not found."), 404
    quiz = decode(quiz, "questions"); data = request.get_json(silent=True) or {}; answers = data.get("answers", {})
    if not isinstance(answers, dict): return jsonify(error="Answers must be an object keyed by question ID."), 400
    wrong, results, correct_tags = [], [], []
    for question in quiz["questions"]:
        correct, answer = grade_question(question, answers.get(question.get("id")))
        result = {"id": question.get("id"), "correct": correct, "answer": answer, "correct_answer": question.get("correct_answer"), "explanation": question.get("explanation"), "concept_tag": question.get("concept_tag")}
        results.append(result)
        if correct: correct_tags.append(str(question.get("concept_tag") or ""))
        else: wrong.append({**result, "question": question.get("question")})
    total, score = len(quiz["questions"]), sum(1 for item in results if item["correct"])
    attempt = execute("INSERT INTO quiz_attempts (quiz_id,student_id,score,total_questions,wrong_answers) VALUES (%s,%s,%s,%s,%s) RETURNING id,score,total_questions,wrong_answers,attempted_at", (quiz_id, session["student_id"], score, total, json.dumps(wrong)))
    saved_gaps = []
    for gap in detect_knowledge_gaps(quiz["title"], quiz.get("subject") or "", quiz["raw_content"], wrong):
        existing = query_one("SELECT id FROM knowledge_gaps WHERE student_id=%s AND note_id=%s AND lower(weak_topic)=lower(%s) ORDER BY updated_at DESC,id DESC LIMIT 1", (session["student_id"], quiz["note_id"], gap["weak_topic"]))
        if existing: row = execute("UPDATE knowledge_gaps SET status=%s,simple_explanation=%s,recommended_action=%s,mini_flowchart=%s,updated_at=CURRENT_TIMESTAMP WHERE id=%s RETURNING id,student_id,note_id,weak_topic,status,simple_explanation,recommended_action,mini_flowchart,updated_at", ("needs_practice", gap["simple_explanation"], gap["recommended_action"], gap["mini_flowchart"], existing["id"]))
        else: row = execute("INSERT INTO knowledge_gaps (student_id,note_id,weak_topic,status,simple_explanation,recommended_action,mini_flowchart) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id,student_id,note_id,weak_topic,status,simple_explanation,recommended_action,mini_flowchart,updated_at", (session["student_id"], quiz["note_id"], gap["weak_topic"], "needs_practice", gap["simple_explanation"], gap["recommended_action"], gap["mini_flowchart"]))
        saved_gaps.append(dict(row))
    wrong_tags = {str(item.get("concept_tag") or "").lower() for item in wrong}
    for tag in {tag for tag in correct_tags if tag}:
        if tag.lower() not in wrong_tags: execute("UPDATE knowledge_gaps SET status='mastered',updated_at=CURRENT_TIMESTAMP WHERE student_id=%s AND note_id=%s AND lower(weak_topic)=lower(%s)", (session["student_id"], quiz["note_id"], tag))
    return jsonify(attempt=decode(attempt, "wrong_answers"), score=score, total_questions=total, percentage=round((score / total) * 100) if total else 0, results=results, knowledge_gaps=saved_gaps)

@quiz_bp.get("/knowledge-gaps")
@signed_in
def list_gaps():
    rows = query_all("SELECT g.id,g.note_id,g.weak_topic,g.status,g.simple_explanation,g.recommended_action,g.mini_flowchart,g.updated_at,n.title AS note_title,n.subject FROM knowledge_gaps g JOIN notes n ON n.id=g.note_id WHERE g.student_id=%s ORDER BY CASE g.status WHEN 'needs_practice' THEN 0 ELSE 1 END,g.updated_at DESC,g.id DESC", (session["student_id"],))
    return jsonify(gaps=[dict(row) for row in rows])

@quiz_bp.post("/knowledge-gaps/<int:gap_id>/status")
@signed_in
def update_gap_status(gap_id):
    data = request.get_json(silent=True) or {}; current = query_one("SELECT id,status FROM knowledge_gaps WHERE id=%s AND student_id=%s", (gap_id, session["student_id"]))
    if not current: return jsonify(error="Knowledge gap not found."), 404
    requested = data.get("status"); status = requested if requested in ("needs_practice", "mastered") else ("mastered" if current["status"] != "mastered" else "needs_practice")
    row = execute("UPDATE knowledge_gaps SET status=%s,updated_at=CURRENT_TIMESTAMP WHERE id=%s AND student_id=%s RETURNING id,note_id,weak_topic,status,simple_explanation,recommended_action,mini_flowchart,updated_at", (status, gap_id, session["student_id"]))
    return jsonify(gap=dict(row))
