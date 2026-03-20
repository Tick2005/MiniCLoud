from flask import Flask, jsonify, request
import csv
import io
import json
import os
import time

import pandas as pd
import pymysql
import requests
from jose import jwt

ISSUER = os.getenv("OIDC_ISSUER", "http://authentication-identity-server:8080/realms/master")
AUDIENCE = os.getenv("OIDC_AUDIENCE", "myapp")
JWKS_URL = f"{ISSUER}/protocol/openid-connect/certs"

DB_HOST = os.getenv("DB_HOST", "relational-database-server")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
DB_NAME = os.getenv("DB_NAME", "minicloud")
STUDENT_DB_NAME = os.getenv("STUDENT_DB_NAME", "studentdb")

_JWKS = None
_TS = 0


app = Flask(__name__)


@app.after_request
def add_cors_headers(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return resp


def get_jwks():
    global _JWKS, _TS
    now = time.time()
    if not _JWKS or now - _TS > 600:
        _JWKS = requests.get(JWKS_URL, timeout=5).json()
        _TS = now
    return _JWKS


def db_connect(database):
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=database,
        port=DB_PORT,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def init_student_schema():
    base = db_connect(DB_NAME)
    with base.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {STUDENT_DB_NAME}")
    base.close()

    conn = db_connect(STUDENT_DB_NAME)
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS students(
                id INT PRIMARY KEY AUTO_INCREMENT,
                student_id VARCHAR(10) NOT NULL UNIQUE,
                fullname VARCHAR(100) NOT NULL,
                dob DATE NOT NULL,
                major VARCHAR(50) NOT NULL
            )
            """
        )
    conn.close()


def normalize_student_payload(payload):
    student_id = str(payload.get("student_id", "")).strip()
    fullname = str(payload.get("fullname", "")).strip()
    dob = str(payload.get("dob", "")).strip()
    major = str(payload.get("major", "")).strip()

    if not student_id or not fullname or not dob or not major:
        raise ValueError("student_id, fullname, dob, major are required")

    return {
        "student_id": student_id,
        "fullname": fullname,
        "dob": dob,
        "major": major,
    }


def serialize_db_row(row):
    out = dict(row)
    if out.get("dob") is not None:
        out["dob"] = out["dob"].isoformat()
    return out


def read_students_json():
    with open("students.json", "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/hello")
def hello():
    return jsonify(message="Hello from App Server!")


@app.get("/student")
def student():
    return jsonify(read_students_json())


@app.get("/secure")
def secure():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return jsonify(error="Missing Bearer token"), 401

    token = auth.split(" ", 1)[1]
    try:
        payload = jwt.decode(
            token,
            get_jwks(),
            algorithms=["RS256"],
            audience=AUDIENCE,
            issuer=ISSUER,
        )
        return jsonify(message="Secure resource OK", preferred_username=payload.get("preferred_username"))
    except Exception as e:
        return jsonify(error=str(e)), 401


@app.get("/students-db")
def list_students_db():
    q = str(request.args.get("q", "")).strip()

    conn = db_connect(STUDENT_DB_NAME)
    with conn.cursor() as cur:
        if q:
            like = f"%{q}%"
            cur.execute(
                """
                SELECT id, student_id, fullname, dob, major
                FROM students
                WHERE student_id LIKE %s OR fullname LIKE %s OR major LIKE %s
                ORDER BY id
                """,
                (like, like, like),
            )
        else:
            cur.execute("SELECT id, student_id, fullname, dob, major FROM students ORDER BY id")
        rows = cur.fetchall()
    conn.close()

    return jsonify([serialize_db_row(r) for r in rows])


@app.get("/students-db/<int:student_pk>")
def get_student_db(student_pk):
    conn = db_connect(STUDENT_DB_NAME)
    with conn.cursor() as cur:
        cur.execute("SELECT id, student_id, fullname, dob, major FROM students WHERE id=%s", (student_pk,))
        row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify(error="Student not found"), 404
    return jsonify(serialize_db_row(row))


@app.post("/students-db")
def create_student_db():
    payload = request.get_json(silent=True) or request.form.to_dict()
    try:
        clean = normalize_student_payload(payload)
    except ValueError as e:
        return jsonify(error=str(e)), 400

    conn = db_connect(STUDENT_DB_NAME)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO students(student_id, fullname, dob, major) VALUES(%s, %s, %s, %s)",
                (clean["student_id"], clean["fullname"], clean["dob"], clean["major"]),
            )
            created_id = cur.lastrowid
            cur.execute("SELECT id, student_id, fullname, dob, major FROM students WHERE id=%s", (created_id,))
            created = cur.fetchone()
    except pymysql.err.IntegrityError:
        conn.close()
        return jsonify(error="student_id already exists"), 409

    conn.close()
    return jsonify(serialize_db_row(created)), 201


@app.put("/students-db/<int:student_pk>")
def update_student_db(student_pk):
    payload = request.get_json(silent=True) or request.form.to_dict()
    try:
        clean = normalize_student_payload(payload)
    except ValueError as e:
        return jsonify(error=str(e)), 400

    conn = db_connect(STUDENT_DB_NAME)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE students
                SET student_id=%s, fullname=%s, dob=%s, major=%s
                WHERE id=%s
                """,
                (clean["student_id"], clean["fullname"], clean["dob"], clean["major"], student_pk),
            )
            if cur.rowcount == 0:
                conn.close()
                return jsonify(error="Student not found"), 404
            cur.execute("SELECT id, student_id, fullname, dob, major FROM students WHERE id=%s", (student_pk,))
            updated = cur.fetchone()
    except pymysql.err.IntegrityError:
        conn.close()
        return jsonify(error="student_id already exists"), 409

    conn.close()
    return jsonify(serialize_db_row(updated))


@app.delete("/students-db/<int:student_pk>")
def delete_student_db(student_pk):
    conn = db_connect(STUDENT_DB_NAME)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM students WHERE id=%s", (student_pk,))
        deleted = cur.rowcount
    conn.close()

    if deleted == 0:
        return jsonify(error="Student not found"), 404
    return jsonify(message="Deleted")


@app.delete("/students-db")
def bulk_delete_students_db():
    payload = request.get_json(silent=True) or {}
    ids = payload.get("ids", [])
    delete_all = bool(payload.get("delete_all", False))

    conn = db_connect(STUDENT_DB_NAME)
    with conn.cursor() as cur:
        if delete_all:
            cur.execute("DELETE FROM students")
            deleted = cur.rowcount
        else:
            if not isinstance(ids, list) or not ids:
                conn.close()
                return jsonify(error="ids is required for bulk delete"), 400
            placeholders = ",".join(["%s"] * len(ids))
            cur.execute(f"DELETE FROM students WHERE id IN ({placeholders})", tuple(ids))
            deleted = cur.rowcount
    conn.close()

    return jsonify(message="Bulk delete completed", deleted=deleted)


@app.post("/students-db/import")
def import_students_db():
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify(error="Missing upload file"), 400

    filename = file.filename.lower()

    if filename.endswith(".csv"):
        text_stream = io.StringIO(file.read().decode("utf-8-sig"))
        reader = csv.DictReader(text_stream)
        rows = list(reader)
    elif filename.endswith(".xlsx") or filename.endswith(".xls"):
        df = pd.read_excel(file)
        rows = df.to_dict(orient="records")
    else:
        return jsonify(error="Only CSV/XLS/XLSX are supported"), 400

    if not rows:
        return jsonify(error="No data in file"), 400

    prepared = []
    skipped = 0
    for row in rows:
        try:
            prepared.append(normalize_student_payload(row))
        except ValueError:
            skipped += 1

    if not prepared:
        return jsonify(error="No valid rows found"), 400

    conn = db_connect(STUDENT_DB_NAME)
    inserted = 0
    duplicates = 0
    with conn.cursor() as cur:
        for item in prepared:
            try:
                cur.execute(
                    "INSERT INTO students(student_id, fullname, dob, major) VALUES(%s, %s, %s, %s)",
                    (item["student_id"], item["fullname"], item["dob"], item["major"]),
                )
                inserted += 1
            except pymysql.err.IntegrityError:
                duplicates += 1
    conn.close()

    return jsonify(
        message="Import finished",
        inserted=inserted,
        duplicates=duplicates,
        skipped=skipped,
        total_in_file=len(rows),
    )


init_student_schema()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
