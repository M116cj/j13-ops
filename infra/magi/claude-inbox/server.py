"""claude-inbox server — FastAPI + token auth

環境變數:
  CLAUDE_INBOX_TOKEN  必填，Bearer token 認證
  INBOX_DIR           選填，預設 /data
"""

import os
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, Request, HTTPException, Depends, Form
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

app = FastAPI(title="claude-inbox", docs_url=None, redoc_url=None)

INBOX_DIR = Path(os.getenv("INBOX_DIR", "/data"))
INBOX_DIR.mkdir(parents=True, exist_ok=True)

TOKEN = os.getenv("CLAUDE_INBOX_TOKEN", "")
if not TOKEN:
    raise RuntimeError("CLAUDE_INBOX_TOKEN env var is required")

security = HTTPBearer(auto_error=False)

MOBILE_CSS = """
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       margin: 0; padding: 16px; background: #0f0f1a; color: #e0e0e0; min-height: 100vh; }
h2 { color: #7eb8f7; margin: 0 0 20px; font-size: 1.3rem; }
label { display: block; margin-bottom: 4px; color: #aaa; font-size: 0.85rem; }
input[type=text], input[type=password], textarea {
  width: 100%; padding: 12px; border-radius: 8px;
  background: #1a1a2e; color: #e0e0e0;
  border: 1px solid #2a2a4a; font-size: 1rem; margin-bottom: 14px; }
textarea { height: 180px; resize: vertical; }
button {
  width: 100%; padding: 14px; border-radius: 8px; border: none;
  background: #4a7cf7; color: white; font-size: 1rem;
  font-weight: 600; cursor: pointer; }
button:active { background: #3a6ce0; }
.card { background: #1a1a2e; border-radius: 12px; padding: 20px; margin-bottom: 12px; }
.file-item { padding: 10px 0; border-bottom: 1px solid #2a2a4a;
             display: flex; justify-content: space-between; align-items: center; }
.file-item:last-child { border-bottom: none; }
.file-name { color: #7eb8f7; font-size: 0.9rem; word-break: break-all; }
.file-meta { color: #666; font-size: 0.75rem; margin-top: 2px; }
.badge { background: #4a7cf7; color: white; padding: 3px 8px;
         border-radius: 12px; font-size: 0.75rem; text-decoration: none; }
.error { background: #2a1a1a; border: 1px solid #e94560;
         color: #e94560; padding: 12px; border-radius: 8px; margin-bottom: 14px; }
"""


async def verify_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if credentials and credentials.credentials == TOKEN:
        return True
    if request.query_params.get("token") == TOKEN:
        return True
    raise HTTPException(status_code=401, detail="Invalid or missing token")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/login", response_class=HTMLResponse)
async def login_page(error: str = ""):
    err_html = '<div class="error">❌ 密碼錯誤，請重試</div>' if error else ""
    return f"""<!DOCTYPE html>
<html><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude Inbox</title>
<style>{MOBILE_CSS}</style>
</head><body>
<div class="card">
  <h2>🔐 Claude Inbox</h2>
  {err_html}
  <form method="post" action="/login">
    <label>密碼（Token）</label>
    <input type="password" name="token" placeholder="輸入 token" autofocus required>
    <button type="submit">進入</button>
  </form>
</div>
</body></html>"""


@app.post("/login")
async def login_submit(token: str = Form(...)):
    if token == TOKEN:
        return RedirectResponse(url=f"/?token={token}", status_code=303)
    return RedirectResponse(url="/login?error=1", status_code=303)


@app.get("/", response_class=HTMLResponse)
async def web_ui(request: Request, auth: bool = Depends(verify_token)):
    token = request.query_params.get("token", TOKEN)
    files = sorted(INBOX_DIR.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True) if INBOX_DIR.exists() else []
    file_items = ""
    for f in files:
        if f.is_file():
            size = f.stat().st_size
            size_str = f"{size}B" if size < 1024 else f"{size//1024}KB"
            file_items += f"""
            <div class="file-item">
              <div>
                <div class="file-name">{f.name}</div>
                <div class="file-meta">{size_str}</div>
              </div>
              <a class="badge" href="/files/{f.name}?token={token}">查看</a>
            </div>"""

    files_section = f"""
    <div class="card">
      <h2>📂 已上傳（{len(files)} 筆）</h2>
      {file_items if file_items else '<div style="color:#666">尚無檔案</div>'}
    </div>""" if files else ""

    return f"""<!DOCTYPE html>
<html><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude Inbox</title>
<style>{MOBILE_CSS}</style>
</head><body>
<div class="card">
  <h2>📨 Claude Inbox</h2>
  <form method="post" action="/submit?token={token}">
    <label>檔名（留空自動產生）</label>
    <input type="text" name="filename" placeholder="例：notes.txt">
    <label>內容</label>
    <textarea name="content" placeholder="在此貼上內容…" required></textarea>
    <button type="submit">📤 上傳</button>
  </form>
</div>
{files_section}
</body></html>"""


@app.post("/submit")
async def submit(request: Request, auth: bool = Depends(verify_token)):
    form = await request.form()
    content = form.get("content", "")
    if not content:
        raise HTTPException(400, "content is required")

    filename = form.get("filename", "").strip()
    if not filename:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        filename = f"inbox-{ts}.txt"

    filename = Path(filename).name
    filepath = INBOX_DIR / filename
    filepath.write_text(content if isinstance(content, str) else content.decode())

    token = request.query_params.get("token", "")
    return RedirectResponse(url=f"/?token={token}", status_code=303)


@app.get("/files/{name}")
async def get_file(name: str, auth: bool = Depends(verify_token)):
    filepath = INBOX_DIR / Path(name).name
    if not filepath.exists():
        raise HTTPException(404, "not found")
    return PlainTextResponse(filepath.read_text())
