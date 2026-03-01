from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
import requests as http_requests
import random, asyncio, json, os, time, secrets
from datetime import datetime
from collections import deque

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

security = HTTPBasic()

# ── Admin credentials ──────────────────────────────────────
# NEVER hardcode credentials here.
# Set these as environment variables on your server:
#   export ADMIN_USER="your_username"
#   export ADMIN_PASS="your_secure_password"
# Or use a .env file (add .env to .gitignore!)
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "changeme")  # <── change via env var

# ── LibreTranslate ─────────────────────────────────────────
LIBRETRANSLATE_URL = os.environ.get("LIBRETRANSLATE_URL", "http://127.0.0.1:5001/translate")

# ── Log: letzte 40 Eingaben im RAM ────────────────────────
log_entries = deque(maxlen=40)

def log_input(text: str, rounds: int, source: str, target: str, ip: str):
    log_entries.appendleft({
        "time": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "ip": ip,
        "chars": len(text),
        "rounds": rounds,
        "source": source,
        "target": target,
        "text": text[:500]  # max 500 chars stored
    })

def check_admin(credentials: HTTPBasicCredentials = Depends(security)):
    ok_user = secrets.compare_digest(credentials.username, ADMIN_USER)
    ok_pass = secrets.compare_digest(credentials.password, ADMIN_PASS)
    if not (ok_user and ok_pass):
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Basic"}, detail="Falsches Passwort")
    return credentials.username

# ── Languages (LibreTranslate supported) ───────────────────
LANGUAGES = [
    ("ar", "Arabisch"),
    ("cs", "Tschechisch"),
    ("de", "Deutsch"),
    ("en", "Englisch"),
    ("es", "Spanisch"),
    ("fi", "Finnisch"),
    ("fr", "Französisch"),
    ("hu", "Ungarisch"),
    ("it", "Italienisch"),
    ("ja", "Japanisch"),
    ("ko", "Koreanisch"),
    ("nl", "Niederländisch"),
    ("pl", "Polnisch"),
    ("pt", "Portugiesisch"),
    ("ro", "Rumänisch"),
    ("ru", "Russisch"),
    ("sv", "Schwedisch"),
    ("tr", "Türkisch"),
    ("uk", "Ukrainisch"),
    ("zh", "Chinesisch"),
]
LANG_DICT = {code: name for code, name in LANGUAGES}

class TranslateRequest(BaseModel):
    text: str
    rounds: int = 10
    source: str = "auto"
    target: str = "de"
    engine: str = "libretranslate"  # "libretranslate" or "google"

def do_translate(text: str, src: str, tgt: str, engine: str = "libretranslate") -> str:
    if engine == "google":
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source=src, target=tgt).translate(text)
    else:
        payload = {
            "q": text,
            "source": src if src != "auto" else "auto",
            "target": tgt,
            "format": "text"
        }
        resp = http_requests.post(LIBRETRANSLATE_URL, json=payload, timeout=30)
        if resp.status_code != 200:
            raise Exception(f"LibreTranslate error: {resp.status_code} – {resp.text}")
        return resp.json()["translatedText"]

# ── Routes ─────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    p = os.path.join(os.path.dirname(__file__), "index.html")
    return HTMLResponse(open(p, encoding="utf-8").read())

@app.get("/datenschutz", response_class=HTMLResponse)
async def datenschutz():
    p = os.path.join(os.path.dirname(__file__), "datenschutz.html")
    return HTMLResponse(open(p, encoding="utf-8").read())

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(user: str = Depends(check_admin)):
    entries = list(log_entries)

    cards = ""
    for i, e in enumerate(entries):
        text_preview = e['text'].replace('<', '&lt;').replace('>', '&gt;').replace('\n', ' ')
        cards += f"""
        <div class="entry">
          <div class="entry-meta">
            <span class="entry-time">{e['time']}</span>
            <span class="entry-num">#{len(entries)-i}</span>
          </div>
          <div class="entry-text">{text_preview}</div>
          <div class="entry-tags">
            <span class="tag">{e['ip']}</span>
            <span class="tag">{e['chars']} chars</span>
            <span class="tag">{e['rounds']} rounds</span>
            <span class="tag">{e['source']} → {e['target']}</span>
          </div>
        </div>"""

    if not cards:
        cards = '<div class="empty">No entries yet.</div>'

    total_rounds = sum(e['rounds'] for e in entries)
    avg_chars = round(sum(e['chars'] for e in entries) / max(len(entries), 1))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Admin – HyperTranslate</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
  --bg: #111110; --surface: #1a1a18; --border: #2e2e2b;
  --text: #e8e6e0; --muted: #6b6b65; --subtle: #3a3a36;
  --accent: #d4a853; --blue: #5b9cf6;
  --mono: 'IBM Plex Mono', monospace;
  --sans: 'IBM Plex Sans', sans-serif;
}}
body {{ font-family: var(--sans); background: var(--bg); color: var(--text); min-height: 100vh; }}
.wrap {{ max-width: 680px; margin: 0 auto; padding: 3rem 1.25rem 3rem; }}
.top {{ margin-bottom: 2.5rem; }}
.top-label {{ font-family: var(--mono); font-size: 0.65rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); margin-bottom: 0.4rem; }}
.top-title {{ font-size: 1.4rem; font-weight: 300; letter-spacing: -0.01em; }}
.top-sub {{ font-family: var(--mono); font-size: 0.65rem; color: var(--muted); margin-top: 0.3rem; }}
.top-sub a {{ color: var(--muted); text-decoration: underline; text-underline-offset: 3px; }}
.stats {{ display: grid; grid-template-columns: repeat(3, 1fr); border: 1px solid var(--border); border-radius: 6px; overflow: hidden; margin-bottom: 2rem; }}
.stat {{ padding: 1rem 1.1rem; border-right: 1px solid var(--border); }}
.stat:last-child {{ border-right: none; }}
.stat-val {{ font-family: var(--mono); font-size: 1.5rem; font-weight: 500; color: var(--blue); line-height: 1; }}
.stat-label {{ font-family: var(--mono); font-size: 0.6rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin-top: 0.35rem; }}
.section-label {{ font-family: var(--mono); font-size: 0.65rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); margin-bottom: 0.875rem; }}
.entry {{ border: 1px solid var(--border); border-radius: 6px; padding: 1rem 1.1rem; margin-bottom: 0.625rem; background: var(--surface); }}
.entry-meta {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem; }}
.entry-time {{ font-family: var(--mono); font-size: 0.65rem; color: var(--muted); }}
.entry-num {{ font-family: var(--mono); font-size: 0.65rem; color: var(--subtle); }}
.entry-text {{ font-size: 0.9rem; font-weight: 300; line-height: 1.6; color: var(--text); margin-bottom: 0.75rem; word-break: break-word; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }}
.entry-tags {{ display: flex; gap: 0.4rem; flex-wrap: wrap; }}
.tag {{ font-family: var(--mono); font-size: 0.6rem; padding: 0.2rem 0.45rem; background: transparent; border: 1px solid var(--border); border-radius: 3px; color: var(--muted); }}
.empty {{ font-family: var(--mono); font-size: 0.75rem; color: var(--muted); text-align: center; padding: 3rem 0; border: 1px solid var(--border); border-radius: 6px; }}
footer {{ border-top: 1px solid var(--border); margin-top: 2.5rem; padding-top: 1.25rem; font-family: var(--mono); font-size: 0.62rem; color: var(--muted); display: flex; justify-content: space-between; }}
footer a {{ color: var(--muted); text-decoration: none; }}
footer a:hover {{ color: var(--text); }}
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <div class="top-label">HyperTranslate / Admin</div>
    <div class="top-title">Input Log</div>
    <div class="top-sub">Signed in as {user} &nbsp;·&nbsp; {len(entries)} of 40 slots used &nbsp;·&nbsp; <a href="/">← back to app</a></div>
  </div>
  <div class="stats">
    <div class="stat"><div class="stat-val">{len(entries)}</div><div class="stat-label">Entries</div></div>
    <div class="stat"><div class="stat-val">{total_rounds}</div><div class="stat-label">Total rounds</div></div>
    <div class="stat"><div class="stat-val">{avg_chars}</div><div class="stat-label">Avg chars</div></div>
  </div>
  <div class="section-label">Recent inputs — newest first</div>
  {cards}
  <footer>
    <span>© 2026 NNW Studios</span>
    <span><a href="https://nnws.qzz.io">nnws.qzz.io</a></span>
  </footer>
</div>
</body>
</html>"""
    return HTMLResponse(html)

@app.get("/api/languages")
async def languages():
    return [{"code": c, "name": n} for c, n in LANGUAGES]

@app.post("/api/translate/stream")
async def translate_stream(req: TranslateRequest, request: Request):
    if not req.text.strip():
        raise HTTPException(400, "Text ist leer")
    if req.rounds < 1 or req.rounds > 1000:
        raise HTTPException(400, "Runden: 1–1000")
    if len(req.text) > 10000:
        raise HTTPException(400, "Max. 10.000 Zeichen")

    ip = request.client.host if request.client else "unknown"
    log_input(req.text, req.rounds, req.source, req.target, ip)

    if req.engine == "google":
        from deep_translator import GoogleTranslator
        lang_pool = LANGUAGES
    else:
        lang_pool = LANGUAGES

    async def generate():
        text = req.text
        src = req.source
        loop = asyncio.get_event_loop()
        used_langs = []

        for i in range(req.rounds):
            is_last = (i == req.rounds - 1)
            if is_last:
                tgt = req.target
            else:
                choices = [c for c, _ in lang_pool if c != src and c != req.target]
                tgt = random.choice(choices)

            try:
                text = await loop.run_in_executor(None, do_translate, text, src, tgt, req.engine)
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                return

            lang_name = LANG_DICT.get(tgt, tgt)
            used_langs.append(lang_name)

            payload = {
                "step": i + 1,
                "total": req.rounds,
                "lang_code": tgt,
                "lang_name": lang_name,
                "text": text,
                "done": is_last,
                "used_langs": used_langs
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            src = tgt
            if not is_last:
                await asyncio.sleep(0.08)

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
