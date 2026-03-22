from flask import Flask, jsonify, render_template, request
import json
import os
import time
from datetime import datetime

import requests
import pymysql
from jose import jwt

ISSUER = os.getenv("OIDC_ISSUER", "http://authentication-identity-server:8080/realms/master")
AUDIENCE = os.getenv("OIDC_AUDIENCE", "myapp")
JWKS_URL = f"{ISSUER}/protocol/openid-connect/certs"

_JWKS = None; _TS = 0
def get_jwks():
    global _JWKS, _TS
    now = time.time()
    if not _JWKS or now - _TS > 600:
        _JWKS = requests.get(JWKS_URL, timeout=5).json()
        _TS = now
    return _JWKS

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDENTS_JSON_PATH = os.path.join(BASE_DIR, "students.json")

DB_HOST = os.getenv("DB_HOST", "relational-database-server")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
DB_NAME = os.getenv("DB_NAME", "studentdb")

MAX_STUDENT_ID_LEN = 10
MAX_FULLNAME_LEN = 100
MAX_MAJOR_LEN = 50


def get_db_connection(database=DB_NAME):
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=database,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5,
        autocommit=True,
    )


def parse_ids(raw_ids):
    ids = []
    if not raw_ids:
        return ids
    for item in raw_ids.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            ids.append(int(item))
        except ValueError:
            continue
    return ids


def validate_student_payload(student_id, fullname, dob, major):
    if len(student_id) > MAX_STUDENT_ID_LEN:
        return f"student_id must be <= {MAX_STUDENT_ID_LEN} characters"
    if len(fullname) > MAX_FULLNAME_LEN:
        return f"fullname must be <= {MAX_FULLNAME_LEN} characters"
    if len(major) > MAX_MAJOR_LEN:
        return f"major must be <= {MAX_MAJOR_LEN} characters"
    try:
        datetime.strptime(dob, "%Y-%m-%d")
    except ValueError:
        return "dob must be in YYYY-MM-DD format"
    return None


def normalize_dob_value(value):
    if value is None:
        return ""

    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")

    value_str = str(value)
    known_formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%a, %d %b %Y %H:%M:%S %Z",
    ]
    for fmt in known_formats:
        try:
            return datetime.strptime(value_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    if len(value_str) >= 10 and value_str[4:5] == "-" and value_str[7:8] == "-":
        return value_str[:10]
    return value_str


def normalize_student_row(row):
    if not row:
        return row
    row["dob"] = normalize_dob_value(row.get("dob"))
    return row


def normalize_student_rows(rows):
    return [normalize_student_row(row) for row in rows]


def should_render_html():
    render_format = (request.args.get("format") or "").lower()
    if render_format == "json":
        return False
    if render_format == "html":
        return True
    return request.headers.get("X-Render-Mode", "").lower() == "html"

@app.get("/hello")
def hello(): return jsonify(message="Hello from App Server!")


@app.get("/")
def app_home():
    return jsonify(
        service="application-backend-server",
        routes=["/hello", "/secure", "/student", "/students-db"],
    )


@app.get("/student")
def student():
    if should_render_html():
        return render_template("student.html")

    with open(STUDENTS_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)


@app.get("/students-db")
def students_db():
    if should_render_html():
        return render_template("students_db.html")

    q = request.args.get("q", "").strip()
    ids = parse_ids(request.args.get("ids", ""))
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            sql = "SELECT id, student_id, fullname, dob, major FROM students"
            params = []

            if ids:
                placeholders = ",".join(["%s"] * len(ids))
                sql += f" WHERE id IN ({placeholders})"
                params.extend(ids)
            elif q:
                sql += " WHERE student_id LIKE %s OR fullname LIKE %s OR major LIKE %s"
                like_q = f"%{q}%"
                params.extend([like_q, like_q, like_q])

            sql += " ORDER BY id"
            cur.execute(sql, params)
            rows = cur.fetchall()
        return jsonify(normalize_student_rows(rows))
    finally:
        conn.close()


@app.get("/students-db/<int:row_id>")
def students_db_one(row_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, student_id, fullname, dob, major FROM students WHERE id = %s",
                (row_id,),
            )
            row = cur.fetchone()
        if not row:
            return jsonify(error="Student not found"), 404
        return jsonify(normalize_student_row(row))
    finally:
        conn.close()


@app.post("/students-db")
def students_db_create():
    data = request.get_json(silent=True) or {}
    student_id = (data.get("student_id") or "").strip()
    fullname = (data.get("fullname") or "").strip()
    dob = (data.get("dob") or "").strip()
    major = (data.get("major") or "").strip()

    if not all([student_id, fullname, dob, major]):
        return jsonify(error="student_id, fullname, dob, major are required"), 400

    validation_error = validate_student_payload(student_id, fullname, dob, major)
    if validation_error:
        return jsonify(error=validation_error), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO students(student_id, fullname, dob, major) VALUES (%s, %s, %s, %s)",
                (student_id, fullname, dob, major),
            )
            new_id = cur.lastrowid
            cur.execute(
                "SELECT id, student_id, fullname, dob, major FROM students WHERE id = %s",
                (new_id,),
            )
            row = cur.fetchone()
        return jsonify(normalize_student_row(row)), 201
    finally:
        conn.close()


@app.put("/students-db/<int:row_id>")
def students_db_update(row_id):
    data = request.get_json(silent=True) or {}
    allowed_fields = ["student_id", "fullname", "dob", "major"]
    updates = []
    params = []

    existing_row = None
    for field in allowed_fields:
        if field in data:
            value = data[field]
            if isinstance(value, str):
                value = value.strip()
            updates.append(f"{field} = %s")
            params.append(value)

    if not updates:
        return jsonify(error="No fields to update"), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, student_id, fullname, dob, major FROM students WHERE id = %s",
                (row_id,),
            )
            existing_row = cur.fetchone()
            if not existing_row:
                return jsonify(error="Student not found"), 404

            merged_student_id = data.get("student_id", existing_row["student_id"])
            merged_fullname = data.get("fullname", existing_row["fullname"])
            merged_dob = data.get("dob", existing_row["dob"])
            merged_major = data.get("major", existing_row["major"])

            if merged_dob is not None and not isinstance(merged_dob, str):
                merged_dob = str(merged_dob)

            validation_error = validate_student_payload(
                str(merged_student_id).strip(),
                str(merged_fullname).strip(),
                str(merged_dob).strip(),
                str(merged_major).strip(),
            )
            if validation_error:
                return jsonify(error=validation_error), 400

            sql = f"UPDATE students SET {', '.join(updates)} WHERE id = %s"
            params.append(row_id)
            cur.execute(sql, params)
            cur.execute(
                "SELECT id, student_id, fullname, dob, major FROM students WHERE id = %s",
                (row_id,),
            )
            row = cur.fetchone()
        return jsonify(normalize_student_row(row))
    finally:
        conn.close()


@app.delete("/students-db/<int:row_id>")
def students_db_delete_one(row_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM students WHERE id = %s", (row_id,))
            deleted = cur.rowcount
        if deleted == 0:
            return jsonify(error="Student not found"), 404
        return jsonify(message="Deleted", deleted=deleted)
    finally:
        conn.close()


@app.delete("/students-db")
def students_db_delete_many():
    delete_all = request.args.get("all", "false").lower() == "true"
    ids = parse_ids(request.args.get("ids", ""))

    if not delete_all and not ids:
        return jsonify(error="Provide ids or all=true"), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if delete_all:
                cur.execute("DELETE FROM students")
                deleted = cur.rowcount
            else:
                placeholders = ",".join(["%s"] * len(ids))
                cur.execute(f"DELETE FROM students WHERE id IN ({placeholders})", ids)
                deleted = cur.rowcount
        return jsonify(message="Deleted", deleted=deleted)
    finally:
        conn.close()

@app.get("/secure")
def secure():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return jsonify(error="Missing Bearer token"), 401
    token = auth.split(" ",1)[1]
    try:
        payload = jwt.decode(token, get_jwks(), algorithms=["RS256"], audience=AUDIENCE, issuer=ISSUER)
        return jsonify(message="Secure resource OK", preferred_username=payload.get("preferred_username"))
    except Exception as e:
        return jsonify(error=str(e)), 401

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
