"""Personal learning analytics and idempotent presentation demo data."""
import json
import os
from datetime import date, timedelta
from functools import wraps
from flask import Blueprint, jsonify, session
from api.db import execute, query_all, query_one, using_postgres
from api.gemini_service import generate_quiz_and_flashcards, generate_smart_revision_plan

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")

def signed_in(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("student_id"): return jsonify(error="Please sign in to view analytics."), 401
        return view(*args, **kwargs)
    return wrapped

def count(sql, student_id): return query_one(sql, (student_id,))["count"]

def plan_progress(student_id):
    row = query_one("SELECT schedule FROM revision_plans WHERE student_id=%s ORDER BY created_at DESC,id DESC LIMIT 1", (student_id,))
    if not row: return 0
    schedule = row["schedule"] if not isinstance(row["schedule"], str) else json.loads(row["schedule"])
    tasks = [task for day in schedule for task in day.get("tasks", [])]
    return round(sum(bool(task.get("done")) for task in tasks) * 100 / len(tasks)) if tasks else 0

def overview(student_id):
    total_notes = count("SELECT COUNT(*) AS count FROM notes WHERE student_id=%s", student_id)
    total_quizzes = count("SELECT COUNT(*) AS count FROM quizzes WHERE student_id=%s", student_id)
    total_attempts = count("SELECT COUNT(*) AS count FROM quiz_attempts WHERE student_id=%s", student_id)
    avg = query_one("SELECT AVG(CASE WHEN total_questions>0 THEN score*100.0/total_questions END) AS value FROM quiz_attempts WHERE student_id=%s", (student_id,))["value"]
    gaps = count("SELECT COUNT(*) AS count FROM knowledge_gaps WHERE student_id=%s AND status='needs_practice'", student_id)
    mastered = count("SELECT COUNT(*) AS count FROM knowledge_gaps WHERE student_id=%s AND status='mastered'", student_id)
    chat_questions = count("SELECT COUNT(*) AS count FROM chat_messages WHERE student_id=%s AND role='user'", student_id)
    rows = query_all("""SELECT n.id,n.title,n.subject,COUNT(a.id) AS attempts,MAX(CASE WHEN a.total_questions>0 THEN a.score*100.0/a.total_questions END) AS best_score,
                     (SELECT a2.score*100.0/a2.total_questions FROM quiz_attempts a2 JOIN quizzes q2 ON q2.id=a2.quiz_id WHERE q2.note_id=n.id AND a2.student_id=n.student_id ORDER BY a2.attempted_at DESC,a2.id DESC LIMIT 1) AS latest_score,
                     (SELECT COUNT(*) FROM knowledge_gaps g WHERE g.note_id=n.id AND g.student_id=n.student_id AND g.status='needs_practice') AS active_gaps
                     FROM notes n LEFT JOIN quizzes q ON q.note_id=n.id AND q.student_id=n.student_id LEFT JOIN quiz_attempts a ON a.quiz_id=q.id AND a.student_id=n.student_id WHERE n.student_id=%s GROUP BY n.id,n.title,n.subject,n.student_id ORDER BY active_gaps DESC,n.created_at DESC""", (student_id,))
    mastery=[]
    for row in rows:
        score = row["latest_score"] if row["latest_score"] is not None else row["best_score"]
        status = "Needs Practice" if row["active_gaps"] or (score is not None and score < 50) else ("Strong" if score is not None and score >= 80 else "Improving")
        mastery.append({"note_id":row["id"],"note_title":row["title"],"subject":row["subject"] or "Study notes","attempts":row["attempts"],"score_percentage":round(score or 0),"mastery_status":status,"active_gaps":row["active_gaps"]})
    activity=[]
    for row in query_all("SELECT title,created_at FROM notes WHERE student_id=%s ORDER BY created_at DESC,id DESC LIMIT 4",(student_id,)): activity.append({"type":"note","text":f"Created smart note: {row['title']}","at":row["created_at"]})
    for row in query_all("SELECT a.score,a.total_questions,a.attempted_at,n.title FROM quiz_attempts a JOIN quizzes q ON q.id=a.quiz_id JOIN notes n ON n.id=q.note_id WHERE a.student_id=%s ORDER BY a.attempted_at DESC,a.id DESC LIMIT 4",(student_id,)): activity.append({"type":"quiz","text":f"Completed quiz for {row['title']} ({row['score']}/{row['total_questions']})","at":row["attempted_at"]})
    for row in query_all("SELECT weak_topic,status,updated_at FROM knowledge_gaps WHERE student_id=%s ORDER BY updated_at DESC,id DESC LIMIT 4",(student_id,)): activity.append({"type":"gap","text":f"{row['status'].replace('_',' ').title()}: {row['weak_topic']}","at":row["updated_at"]})
    activity.sort(key=lambda item: str(item["at"]), reverse=True)
    next_step = ({"title":"Review a knowledge gap","text":f"Start with {mastery[0]['note_title']} and address its weak concepts.","view":"gaps"} if gaps and mastery else ({"title":"Take your first quiz","text":"Use active recall to see which concepts need more attention.","view":"quiz"} if total_notes and not total_attempts else {"title":"Create your first smart note","text":"Add course material to unlock your study tools.","view":"notes"}))
    return {"counts":{"total_notes":total_notes,"total_quizzes":total_quizzes,"total_attempts":total_attempts,"average_score":round(avg or 0),"needs_practice_gaps":gaps,"mastered_gaps":mastered,"chat_questions_asked":chat_questions,"revision_completion_pct":plan_progress(student_id)},"subject_mastery":mastery,"recent_activity":activity[:8],"recommended_next_step":next_step,"system_status":{"database_mode":"postgresql" if using_postgres() else "sqlite_fallback","ai_mode":"gemini_live" if os.getenv("GEMINI_API_KEY") else "deterministic_fallback"}}

@analytics_bp.route("", methods=["GET"], strict_slashes=False)
@analytics_bp.route("/", methods=["GET"], strict_slashes=False)
@analytics_bp.get("/overview")
@signed_in
def get_overview(): return jsonify(overview(session["student_id"]))

@analytics_bp.post("/seed-demo")
@signed_in
def seed_demo():
    student_id=session["student_id"]
    existing=query_one("SELECT id FROM notes WHERE student_id=%s AND title='Photosynthesis & Cellular Energy'",(student_id,))
    if existing: return jsonify(message="Sample presentation data is already loaded.",seeded=False,overview=overview(student_id))
    data=[("Photosynthesis & Cellular Energy","Biology","Photosynthesis uses light energy to convert water and carbon dioxide into glucose and oxygen. Chlorophyll in chloroplasts captures light. Light-dependent reactions produce ATP and NADPH. The Calvin cycle uses these molecules to fix carbon dioxide into sugar.","Photosynthesis stores solar energy as chemical energy. Light reactions capture energy, while the Calvin cycle builds sugar.",["Chlorophyll absorbs light energy.","Light reactions produce ATP and NADPH.","The Calvin cycle fixes carbon dioxide.","Glucose stores chemical energy.","Oxygen is released as a product."],[{"term":"Chlorophyll","definition":"A pigment that absorbs light energy."},{"term":"Calvin Cycle","definition":"A process that fixes carbon dioxide into sugar."}]),("How CPU & Operating Systems Work","Computer Science","A CPU runs programs through the fetch decode execute cycle. The operating system manages hardware resources, processes, memory, files, and input output. Pipelining overlaps instruction stages to improve throughput.","The CPU executes instructions in stages while the operating system coordinates hardware and software resources.",["The CPU fetches an instruction from memory.","Decode determines what the instruction means.","Execute performs the operation.","The operating system manages processes and memory.","Pipelining overlaps instruction work."],[{"term":"CPU","definition":"The processor that executes program instructions."},{"term":"Pipelining","definition":"Overlapping instruction stages to improve throughput."}])]
    created=[]
    for title,subject,raw,summary,points,definitions in data:
        flow="flowchart TD\n  A[\"Input and review\"] --> B[\"Core process\"]\n  B --> C[\"Output and recall\"]"; mind=f"graph LR\n  A[\"{title}\"] --> B[\"Core concepts\"]\n  A --> C[\"Key definitions\"]"
        note=execute("INSERT INTO notes (student_id,title,subject,raw_content,summary,key_points,definitions,flowchart_mermaid,mindmap_mermaid) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id,title,subject,raw_content,summary,key_points,definitions",(student_id,title,subject,raw,summary,json.dumps(points),json.dumps(definitions),flow,mind))
        note=dict(note);note["key_points"]=points;note["definitions"]=definitions;created.append(note)
    quiz_ids=[]
    for note in created:
        assessment=generate_quiz_and_flashcards(note["title"],note["subject"],note["raw_content"],note["summary"],note["key_points"],note["definitions"])
        quiz=execute("INSERT INTO quizzes (note_id,student_id,questions,flashcards) VALUES (%s,%s,%s,%s) RETURNING id",(note["id"],student_id,json.dumps(assessment["questions"]),json.dumps(assessment["flashcards"])));quiz_ids.append(quiz["id"])
    execute("INSERT INTO quiz_attempts (quiz_id,student_id,score,total_questions,wrong_answers) VALUES (%s,%s,%s,%s,%s)",(quiz_ids[0],student_id,3,4,json.dumps([{"concept_tag":"Calvin Cycle Carbon Fixation","question":"Explain carbon fixation","correct_answer":"Carbon dioxide is fixed into sugar"}])))
    gaps=[(created[0]["id"],"Calvin Cycle Carbon Fixation"),(created[1]["id"],"CPU Instruction Pipelining")]
    for note_id,topic in gaps: execute("INSERT INTO knowledge_gaps (student_id,note_id,weak_topic,status,simple_explanation,recommended_action,mini_flowchart) VALUES (%s,%s,%s,'needs_practice',%s,%s,%s)",(student_id,note_id,topic,f"{topic} needs a short focused review.","1. Read the explanation. 2. Trace the process. 3. Retry a quiz question.",f"flowchart TD\n  A[\"Review {topic}\"] --> B[\"Practice example\"] --> C[\"Retry quiz\"]"))
    execute("INSERT INTO chat_messages (student_id,note_id,role,message) VALUES (%s,%s,'user',%s)",(student_id,created[0]["id"],"Photosynthesis ko simple words mein samjhao"));execute("INSERT INTO chat_messages (student_id,note_id,role,message,source_reference) VALUES (%s,%s,'assistant',%s,%s)",(student_id,created[0]["id"],"Simple words mein: plants use light to turn water and carbon dioxide into sugar.","Biology — Photosynthesis & Cellular Energy | Section: Summary"))
    generated=generate_smart_revision_plan(str(date.today()+timedelta(days=7)),2,created,[{"note_id":n,"weak_topic":t,"status":"needs_practice"} for n,t in gaps],[])
    execute("INSERT INTO revision_plans (student_id,exam_date,daily_hours,schedule) VALUES (%s,%s,%s,%s)",(student_id,str(date.today()+timedelta(days=7)),2,json.dumps(generated["schedule"])))
    return jsonify(message="Sample presentation data loaded.",seeded=True,overview=overview(student_id)),201
