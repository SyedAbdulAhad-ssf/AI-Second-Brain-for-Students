"""Flask application for local and Vercel deployment."""
import os
from pathlib import Path
from flask import Flask,jsonify,send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from api.db import init_db
from api.routes.auth_routes import auth_bp
from api.routes.notes_routes import notes_bp
from api.routes.quiz_routes import quiz_bp
from api.routes.rag_routes import rag_bp
from api.routes.analytics_routes import analytics_bp
ROOT=Path(__file__).resolve().parent;load_dotenv(ROOT/".env", override=False)
app=Flask(__name__,static_folder="public",static_url_path="")
app.secret_key=os.getenv("FLASK_SECRET_KEY","dev-only-change-me")
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Lax",SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE","false").lower()=="true")
CORS(app,supports_credentials=True,origins=os.getenv("FRONTEND_ORIGIN","*").split(","))
for bp in (auth_bp,notes_bp,quiz_bp,rag_bp,analytics_bp):app.register_blueprint(bp)
@app.get("/api/health")
def health():
    if not os.getenv("DATABASE_URL"):return jsonify(status="ok",database="not_configured")
    try:init_db();return jsonify(status="ok",database="connected")
    except Exception:app.logger.exception("Database check failed");return jsonify(status="degraded",database="error"),503
@app.get("/")
def home():return send_from_directory(app.static_folder,"index.html")
@app.get("/<path:path>")
def static_files(path):
    if (ROOT/"public"/path).is_file():return send_from_directory(app.static_folder,path)
    return send_from_directory(app.static_folder,"index.html")
with app.app_context():
    try:init_db()
    except Exception:app.logger.exception("Database initialization deferred; check DATABASE_URL and schema privileges")
if __name__=="__main__":app.run(host="0.0.0.0",port=int(os.getenv("PORT","5000")),debug=os.getenv("FLASK_DEBUG","false").lower()=="true")
