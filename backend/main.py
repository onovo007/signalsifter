"""
SignalSifter – FastAPI Backend
Dr. Amobi Andrew Onovo
Run locally:  uvicorn main:app --reload --port 8000
"""
import io
import uuid
import pandas as pd
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from iv_analysis import run_analysis
from agents import iv_expert_agent, general_data_agent

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="SignalSifter API",
    description="Advanced Feature Selection with IV/WoE Analysis & AI-Powered Insights",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten in production: list Netlify domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory session store ───────────────────────────────────────────────────
# Stores DataFrames & IV results keyed by session UUID.
# Suitable for Render's free / starter tier (single instance).
sessions: dict = {}

MAX_SESSIONS = 200   # evict oldest when exceeded


def _evict_if_needed():
    if len(sessions) > MAX_SESSIONS:
        oldest = next(iter(sessions))
        sessions.pop(oldest, None)


# ── Request / response models ─────────────────────────────────────────────────
class AnalyseRequest(BaseModel):
    session_id: str
    target: str
    features: list[str]
    exclude: list[str] = []
    bins: int = 5


class IVAgentRequest(BaseModel):
    session_id: str
    question: str


class GeneralAgentRequest(BaseModel):
    session_id: str
    question: str
    num_cols: list[str] = []
    dep_col: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "SignalSifter API v2.0"}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Accept CSV or TSV, return session_id + column list + preview rows."""
    _evict_if_needed()

    content = await file.read()
    fname = file.filename or ""

    try:
        sep = "\t" if fname.lower().endswith((".tsv", ".txt")) else ","
        df = pd.read_csv(io.BytesIO(content), sep=sep)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot parse file: {e}")

    if df.empty:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    session_id = str(uuid.uuid4())
    sessions[session_id] = {"df": df, "iv_results": None}

    preview = df.head(8).fillna("").astype(str).to_dict(orient="records")
    columns = list(df.columns)

    return {
        "session_id": session_id,
        "rows": len(df),
        "columns": columns,
        "preview": preview,
    }


@app.post("/api/analyse")
def analyse(req: AnalyseRequest):
    """Run IV/WoE analysis and return results + Plotly JSON chart."""
    session = sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Please re-upload your file.")

    df: pd.DataFrame = session["df"]

    if not req.features:
        raise HTTPException(status_code=400, detail="No features selected for analysis.")

    try:
        results = run_analysis(
            df=df,
            target=req.target,
            features=req.features,
            exclude=req.exclude,
            bins=req.bins,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis error: {e}")

    # persist IV results for agents
    sessions[req.session_id]["iv_results"] = results
    return results


@app.post("/api/iv-agent")
def iv_agent(req: IVAgentRequest):
    """Ask the IV-aware expert agent a question about current results."""
    session = sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    iv_results = session.get("iv_results")
    answer = iv_expert_agent(req.question, iv_results)
    return {"answer": answer}


@app.post("/api/general-agent")
def general_agent(req: GeneralAgentRequest):
    """Ask the LangChain general data science agent."""
    session = sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    df: pd.DataFrame = session["df"]
    result = general_data_agent(req.question, df, req.num_cols, req.dep_col)
    return result
