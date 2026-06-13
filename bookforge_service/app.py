"""BookForge web service — multi-user product.

Public:   /  (landing)   /login  /signup
Auth API: /auth/signup  /auth/login  /auth/logout
App:      /app (dashboard, requires login)
Book API: POST /api/jobs · GET /api/library · GET /api/books/{id}/download · GET /api/me
Ops:      /healthz · /api/diag
Accounts + books live in SQLite (db.py); sessions are signed cookies (auth.py).
"""
import os

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from bookforge.model import BookMeta
from bookforge.theme import Theme, TRIM_SIZES, FONT_THEMES
from bookforge import imagegen
from . import db, auth
from .storage import JobStore
from .jobs import JobManager

MAX_BYTES = int(os.environ.get("BOOKFORGE_MAX_MB", "25")) * 1024 * 1024
ART_STYLES = ["emblem", "photo", "photographic", "cinematic", "watercolor", "painterly", "lineart", "abstract"]
HERE = os.path.dirname(__file__)
TPL = os.path.join(HERE, "templates")

app = FastAPI(title="BookForge")
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")
store = JobStore()
jobs = JobManager(store)
try:
    db.init()
except Exception as e:                      # surface clearly in logs, don't die silently
    print(f"[startup] DB init warning: {type(e).__name__}: {e}")


def page(name):
    with open(os.path.join(TPL, name), encoding="utf-8") as f:
        return HTMLResponse(f.read())


def require_user(request: Request):
    u = auth.current_user(request)
    if not u:
        raise HTTPException(401, "Please log in.")
    return u


# ---- pages ----------------------------------------------------------------

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def landing(request: Request):
    if auth.current_user(request):
        return RedirectResponse("/app", status_code=303)
    return page("landing.html")


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return page("login.html")


@app.get("/signup", response_class=HTMLResponse)
def signup_page():
    return page("signup.html")


@app.get("/app", response_class=HTMLResponse)
def app_page(request: Request):
    if not auth.current_user(request):
        return RedirectResponse("/login", status_code=303)
    return page("app.html")


# ---- auth -----------------------------------------------------------------

def _set_session(resp, user_id, secure):
    resp.set_cookie(auth.COOKIE, auth.make_session(user_id), max_age=30 * 86400,
                    httponly=True, samesite="lax", secure=secure)


@app.post("/auth/signup")
async def signup(request: Request):
    body = await request.json()
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    pw = body.get("password") or ""
    if "@" not in email or "." not in email:
        raise HTTPException(400, "Please enter a valid email address.")
    if len(pw) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")
    if db.get_user_by_email(email):
        raise HTTPException(409, "An account with that email already exists.")
    h, salt = auth.hash_password(pw)
    uid = db.create_user(email, name or email.split("@")[0], h, salt)
    resp = JSONResponse({"ok": True})
    _set_session(resp, uid, request.url.scheme == "https")
    return resp


@app.post("/auth/login")
async def login(request: Request):
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    pw = body.get("password") or ""
    u = db.get_user_by_email(email)
    if not u or not auth.verify_password(pw, u["pw_hash"], u["pw_salt"]):
        raise HTTPException(401, "Incorrect email or password.")
    resp = JSONResponse({"ok": True})
    _set_session(resp, u["id"], request.url.scheme == "https")
    return resp


@app.post("/auth/logout")
def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth.COOKIE)
    return resp


@app.get("/api/me")
def me(request: Request):
    u = require_user(request)
    return {"name": u["name"], "email": u["email"]}


# ---- books ----------------------------------------------------------------

@app.post("/api/jobs")
async def create_job(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form("Untitled"),
    subtitle: str = Form(""),
    author: str = Form(""),
    isbn: str = Form(""),
    publisher: str = Form(""),
    year: str = Form(""),
    epigraph: str = Form(""),
    mode: str = Form("bw"),
    trim: str = Form("6x9"),
    font: str = Form("classic"),
    art_style: str = Form("emblem"),
    crop_marks: str = Form("false"),
):
    u = require_user(request)
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(400, "Please upload a Word .docx file.")
    if mode not in ("bw", "color"):
        raise HTTPException(400, "mode must be 'bw' or 'color'.")
    if trim not in TRIM_SIZES:
        raise HTTPException(400, f"trim must be one of {list(TRIM_SIZES)}.")
    if font not in FONT_THEMES:
        raise HTTPException(400, f"font must be one of {list(FONT_THEMES)}.")
    if art_style not in ART_STYLES:
        raise HTTPException(400, f"art_style must be one of {ART_STYLES}.")

    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, f"File exceeds {MAX_BYTES // (1024*1024)} MB limit.")
    if not data:
        raise HTTPException(400, "The uploaded file is empty.")

    book_id = store.new_job_id()
    docx_path = store.save_upload(book_id, file.filename, data)
    meta = BookMeta(title=title, subtitle=subtitle, author=author, isbn=isbn,
                    publisher=publisher, year=year, epigraph=epigraph)
    theme = Theme(trim=trim, mode=mode, crop_marks=(crop_marks.lower() == "true"),
                  font=font, art_style=art_style)
    db.create_book(book_id, u["id"], meta, theme)
    jobs.submit(book_id, docx_path, meta, theme)
    return JSONResponse({"id": book_id, "status": "queued"}, status_code=202)


@app.get("/api/library")
def library(request: Request):
    u = require_user(request)
    out = []
    for b in db.list_books(u["id"]):
        out.append({"id": b["id"], "title": b["title"], "author": b["author"],
                    "status": b["status"], "message": b["message"], "pages": b["pages"],
                    "trim": b["trim"], "mode": b["mode"], "art_style": b["art_style"]})
    return out


@app.get("/api/books/{book_id}/download")
def download(book_id: str, request: Request):
    u = require_user(request)
    b = db.get_book(book_id)
    if not b or b["user_id"] != u["id"]:
        raise HTTPException(404, "Not found.")
    if b["status"] != "done":
        raise HTTPException(409, "This book isn't ready yet.")
    pdf = db.get_book_pdf(book_id)
    if not pdf:
        raise HTTPException(409, "This book isn't ready yet.")
    fname = (b["title"] or "book").replace(" ", "_") + ".pdf"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# ---- ops ------------------------------------------------------------------

@app.get("/healthz")
def healthz():
    return {"ok": True, "ai_images": imagegen.ai_available(), "provider": imagegen.provider()}


@app.get("/api/diag")
def diag():
    return imagegen.diagnose()
