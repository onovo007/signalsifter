# SignalSifter v2.0 — Deployment Guide
### Dr. Amobi Andrew Onovo · Quantium Insights LLC

---

## Architecture

```
┌─────────────────────────┐        ┌──────────────────────────────┐
│   Netlify (Frontend)    │  REST  │   Render (Backend - FastAPI) │
│                         │◄──────►│                              │
│  index.html             │        │  main.py        (routes)     │
│  styles.css             │        │  iv_analysis.py (WoE / IV)   │
│  app.js                 │        │  agents.py      (GPT-4o)     │
└─────────────────────────┘        └──────────────────────────────┘
         (static)                       (Python 3.11, uvicorn)
```

---

## Step 1 — Deploy the Backend on Render

### Option A: Via `render.yaml` (recommended)
1. Push this entire repo to GitHub.
2. Go to [render.com](https://render.com) → **New → Blueprint**.
3. Connect your GitHub repo — Render will detect `render.yaml` automatically.
4. Set the `OPENAI_API_KEY` environment variable in the Render dashboard under **Environment**.
5. Click **Deploy**. Wait for the build to complete (~3-4 minutes).
6. Copy the service URL (e.g. `https://signalsifter-api.onrender.com`).

### Option B: Manual
1. Go to Render → **New → Web Service**.
2. Connect your GitHub repo.
3. **Root Directory**: `backend`
4. **Build Command**: `pip install -r requirements.txt`
5. **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. **Environment Variables**: Add `OPENAI_API_KEY = sk-...`
7. Deploy.

---

## Step 2 — Set the API URL in the Frontend

Open `frontend/app.js` and update line 8:

```javascript
const API_BASE = "https://your-actual-render-url.onrender.com";
```

Or set it at runtime via a `<script>` block in `index.html` before loading `app.js`:

```html
<script>window.SS_API_BASE = "https://your-actual-render-url.onrender.com";</script>
```

---

## Step 3 — Deploy the Frontend on Netlify

### Option A: Drag & drop
1. Build/open the `frontend/` folder.
2. Go to [app.netlify.com](https://app.netlify.com) → **Add new site → Deploy manually**.
3. Drag the `frontend/` folder into the upload zone.
4. Done — Netlify gives you a URL like `https://signalsifter.netlify.app`.

### Option B: Git-connected (auto-deploy on push)
1. Push the repo to GitHub.
2. Netlify → **Add new site → Import an existing project**.
3. Select your repo.
4. **Publish directory**: `frontend`
5. **Build command**: *(leave blank — no build step required)*
6. Deploy.
7. Add a custom domain under **Domain settings** if desired.

---

## Step 4 — Configure CORS (Production Hardening)

Once you have your Netlify domain, update `backend/main.py` to lock down CORS:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-app.netlify.app"],  # your Netlify URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Local Development

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...                       # Windows: set OPENAI_API_KEY=sk-...
uvicorn main:app --reload --port 8000
# API docs: http://localhost:8000/docs
```

### Frontend
```bash
# Option 1: Python
cd frontend
python -m http.server 3000

# Option 2: Node
npx serve frontend -l 3000
```

Then in `app.js` set:
```javascript
const API_BASE = "http://localhost:8000";
```

---

## Environment Variables Summary

| Variable        | Where         | Required | Description          |
|-----------------|---------------|----------|----------------------|
| `OPENAI_API_KEY`| Render        | Yes      | GPT-4o API key       |
| `SS_API_BASE`   | Frontend JS   | Yes      | Render backend URL   |

---

## Notes on Session Storage

The backend stores uploaded DataFrames in an in-memory Python dict keyed by UUID session tokens.

- This works well on Render's Starter and Standard plans (single instance).
- Sessions are cleared on service restart or evicted after 200 concurrent sessions.
- For high-volume production use, replace `sessions` dict in `main.py` with Redis or a cloud object store (S3/GCS).

---

## File Structure

```
signalsifter/
├── backend/
│   ├── main.py           # FastAPI app + routes
│   ├── iv_analysis.py    # WoE / IV / Gini / KS engine
│   ├── agents.py         # GPT-4o IV agent + LangChain general agent
│   └── requirements.txt
├── frontend/
│   ├── index.html        # Single-page app shell
│   ├── styles.css        # Premium CSS design system
│   └── app.js            # All client-side logic
├── render.yaml           # Render deployment blueprint
├── netlify.toml          # Netlify build + headers config
└── DEPLOYMENT.md         # This file
```
