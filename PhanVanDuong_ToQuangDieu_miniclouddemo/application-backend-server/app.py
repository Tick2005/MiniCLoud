from flask import Flask, jsonify, render_template, request
import json
import os
import time
from datetime import datetime

import requests
import pymysql
from jose import jwt

ISSUER = os.getenv("OIDC_ISSUER", "http://authentication-identity-server:8080/auth/realms/master")
AUDIENCE = os.getenv("OIDC_AUDIENCE", "myapp")
JWKS_URL = f"{ISSUER}/protocol/openid-connect/certs"

_JWKS_CACHE = {}


def get_jwks(jwks_url=JWKS_URL):
    now = time.time()
    cached = _JWKS_CACHE.get(jwks_url)
    if not cached or now - cached["ts"] > 600:
        _JWKS_CACHE[jwks_url] = {
            "value": requests.get(jwks_url, timeout=5).json(),
            "ts": now,
        }
    return _JWKS_CACHE[jwks_url]["value"]

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
_SCHEMA_READY = False


def ensure_student_schema():
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return

    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5,
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE DATABASE IF NOT EXISTS studentdb")
            cur.execute("USE studentdb")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS students(
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    student_id VARCHAR(10) NOT NULL,
                    fullname VARCHAR(100) NOT NULL,
                    dob DATE NOT NULL,
                    major VARCHAR(50) NOT NULL
                )
                """
            )
            cur.execute(
                """
                INSERT INTO students(student_id, fullname, dob, major)
                SELECT 'SV001', 'Nguyen Van A', '2002-03-15', 'Computer Science'
                WHERE NOT EXISTS (SELECT 1 FROM students WHERE student_id = 'SV001')
                """
            )
            cur.execute(
                """
                INSERT INTO students(student_id, fullname, dob, major)
                SELECT 'SV002', 'Tran Thi B', '2001-11-02', 'Data Science'
                WHERE NOT EXISTS (SELECT 1 FROM students WHERE student_id = 'SV002')
                """
            )
            cur.execute(
                """
                INSERT INTO students(student_id, fullname, dob, major)
                SELECT 'SV003', 'Le Van C', '2002-07-20', 'Cybersecurity'
                WHERE NOT EXISTS (SELECT 1 FROM students WHERE student_id = 'SV003')
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS blog_comments(
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    article_name VARCHAR(100) NOT NULL,
                    author_name VARCHAR(100) NOT NULL,
                    comment_text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS blog_likes(
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    article_name VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
    finally:
        conn.close()
    _SCHEMA_READY = True


def get_db_connection(database=DB_NAME):
    try:
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
    except Exception:
        ensure_student_schema()
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


def get_blog_like_count(cur, article_name):
    cur.execute(
        "SELECT COALESCE(COUNT(*), 0) AS like_count FROM blog_likes WHERE article_name = %s",
        (article_name,),
    )
    result = cur.fetchone()
    return result["like_count"] if result else 0


def row_to_comment(row):
    return {
        "id": row["id"],
        "author": row["author_name"],
        "text": row["comment_text"],
        "created_at": str(row["created_at"]) if row["created_at"] else None,
    }


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


def get_bearer_token():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    return auth.split(" ", 1)[1]


def verify_token(token, issuer, audience=None, jwks_url=None):
    jwks_uri = jwks_url or f"{issuer}/protocol/openid-connect/certs"
    jwks = get_jwks(jwks_uri)
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    key_data = None
    for jwk in jwks.get("keys", []):
        if jwk.get("kid") == kid:
            key_data = jwk
            break
    if key_data is None:
        raise Exception("Unable to find matching JWK for token")

    options = {"verify_iss": False}
    if not audience:
        options["verify_aud"] = False

    decode_args = {
        "key": key_data,
        "algorithms": ["RS256"],
        "options": options
    }
    if audience:
        decode_args["audience"] = audience

    return jwt.decode(token, **decode_args)


def get_identity_from_payload(payload):
    return (
        payload.get("preferred_username")
        or payload.get("username")
        or payload.get("email")
        or payload.get("sub")
    )

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
    token = get_bearer_token()
    if not token:
        return jsonify(error="Missing Bearer token"), 401
    try:
        payload = verify_token(token, ISSUER, AUDIENCE)
        return jsonify(
            message="Secure resource OK",
            preferred_username=get_identity_from_payload(payload),
        )
    except Exception as e:
        return jsonify(error=str(e)), 401


@app.get("/secure-oidc")
def secure_oidc():
    token = get_bearer_token()
    if not token:
        return jsonify(error="Missing Bearer token"), 401

    issuer = (request.args.get("issuer") or ISSUER).strip()
    audience = (request.args.get("audience") or "").strip() or None
    jwks_url = (request.args.get("jwks_url") or "").strip() or None
    try:
        payload = verify_token(token, issuer, audience, jwks_url=jwks_url)
        return jsonify(
            message="Secure OIDC resource OK",
            issuer=issuer,
            audience=audience or "(not-validated)",
            jwks_url=jwks_url or f"{issuer}/protocol/openid-connect/certs",
            preferred_username=get_identity_from_payload(payload),
        )
    except Exception as e:
        return jsonify(error=str(e), issuer=issuer, audience=audience, jwks_url=jwks_url), 401


@app.get("/blog/likes/<article_name>")
def get_blog_likes(article_name):
    try:
        conn = get_db_connection("studentdb")
        try:
            with conn.cursor() as cur:
                like_count = get_blog_like_count(cur, article_name)
        finally:
            conn.close()
        return jsonify(article=article_name, likes=like_count)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.post("/blog/like/<article_name>")
def add_blog_like(article_name):
    try:
        conn = get_db_connection("studentdb")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO blog_likes (article_name) VALUES (%s)",
                    (article_name,),
                )
                conn.commit()
                like_count = get_blog_like_count(cur, article_name)
        finally:
            conn.close()
        return jsonify(article=article_name, likes=like_count)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.get("/blog/comments/<article_name>")
def get_blog_comments(article_name):
    try:
        conn = get_db_connection("studentdb")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, author_name, comment_text, created_at FROM blog_comments WHERE article_name = %s ORDER BY created_at DESC",
                    (article_name,),
                )
                rows = cur.fetchall()
        finally:
            conn.close()
        comments = [row_to_comment(row) for row in rows]
        return jsonify(article=article_name, comments=comments)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.post("/blog/comment/<article_name>")
def add_blog_comment(article_name):
    try:
        data = request.get_json()
        author = (data.get("author") or "").strip()
        text = (data.get("text") or "").strip()
        
        if not author or not text:
            return jsonify(error="Author and text are required"), 400
        
        if len(author) > 100:
            return jsonify(error="Author name too long"), 400
        if len(text) > 500:
            return jsonify(error="Comment too long"), 400
        
        conn = get_db_connection("studentdb")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO blog_comments (article_name, author_name, comment_text) VALUES (%s, %s, %s)",
                    (article_name, author, text),
                )
                conn.commit()
                comment_id = cur.lastrowid
                cur.execute(
                    "SELECT id, author_name, comment_text, created_at FROM blog_comments WHERE id = %s",
                    (comment_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()
        
        if row:
            comment = row_to_comment(row)
            return jsonify(
                id=comment["id"],
                article=article_name,
                author=comment["author"],
                text=comment["text"],
                created_at=comment["created_at"],
            )
        return jsonify(article=article_name, success=True)
    except Exception as e:
        return jsonify(error=str(e)), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
