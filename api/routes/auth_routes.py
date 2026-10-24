"""Direct username/password auth; no OTP or email verification."""
import re
from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash
from api.db import execute, query_one
auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
def credentials():
    data=request.get_json(silent=True) or {}; username=str(data.get("username","")).strip(); password=str(data.get("password",""))
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,40}",username): return None,(jsonify(error="Username must be 3–40 letters, numbers, dots, dashes, or underscores."),400)
    if not 8<=len(password)<=256: return None,(jsonify(error="Password must be at least 8 characters."),400)
    return (username,password),None
def student(row): return {"id":row["id"],"username":row["username"]} if row else None
@auth_bp.post("/register")
def register():
    pair,error=credentials()
    if error:return error
    username,password=pair
    try: row=execute("INSERT INTO students (username,password) VALUES (%s,%s) RETURNING id,username",(username,generate_password_hash(password)))
    except Exception as exc:
        if getattr(exc,"pgcode",None)=="23505":return jsonify(error="That username is already taken."),409
        raise
    session["student_id"]=row["id"];return jsonify(student=student(row)),201
@auth_bp.post("/login")
def login():
    pair,error=credentials()
    if error:return error
    username,password=pair; row=query_one("SELECT id,username,password FROM students WHERE username=%s",(username,))
    if not row or not check_password_hash(row["password"],password):return jsonify(error="Incorrect username or password."),401
    session["student_id"]=row["id"];return jsonify(student=student(row))
@auth_bp.post("/logout")
def logout(): session.clear();return jsonify(ok=True)
@auth_bp.get("/me")
def me():
    row=query_one("SELECT id,username FROM students WHERE id=%s",(session.get("student_id"),)) if session.get("student_id") else None
    return (jsonify(student=student(row)) if row else (jsonify(error="Not signed in"),401))
