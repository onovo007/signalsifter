"""
SignalSifter – FastAPI Backend (v2.1)
Dr. Amobi Andrew Onovo
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

app = FastAPI(
    title="SignalSifter API",
    description="Advanced Feature Selection with IV/WoE Analysis & AI-Powered Insights",
    version="2.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store
sessions: dict = {}
MAX_SESSIONS = 200

def _evict_if_needed():
    if len(sessions) > MAX_SESSIONS:
        oldest = next(iter(sessions))
        sessions.pop(oldest, None)


# ── Request models ────────────────────────────────────────────────────────────
class AnalyseRequest(BaseModel):
    session_id: str
    target: str
    features: list[str]
    exclude: list[str] = []
    bins: int = 5

class IVAgentRequest(BaseModel):
    session_id: str
    question: str

class ChatMessage(BaseModel):
    role: str
    content: str

class GeneralAgentRequest(BaseModel):
    session_id: str
    question: str
    cat_cols: list[str] = []
    num_cols: list[str] = []
    dep_col: Optional[str] = None
    history: list[ChatMessage] = []   # full conversation history for memory


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "SignalSifter API v2.1"}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
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
    return {
        "session_id": session_id,
        "rows": len(df),
        "columns": list(df.columns),
        "preview": preview,
    }


@app.post("/api/analyse")
def analyse(req: AnalyseRequest):
    session = sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Please re-upload your file.")

    if not req.features:
        raise HTTPException(status_code=400, detail="No features selected.")

    try:
        results = run_analysis(
            df=session["df"],
            target=req.target,
            features=req.features,
            exclude=req.exclude,
            bins=req.bins,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis error: {e}")

    sessions[req.session_id]["iv_results"] = results
    return results


@app.post("/api/iv-agent")
def iv_agent(req: IVAgentRequest):
    session = sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    answer = iv_expert_agent(req.question, session.get("iv_results"))
    return {"answer": answer}


@app.post("/api/general-agent")
def general_agent(req: GeneralAgentRequest):
    session = sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    history = [{"role": m.role, "content": m.content} for m in req.history]

    result = general_data_agent(
        question=req.question,
        df=session["df"],
        cat_cols=req.cat_cols,
        num_cols=req.num_cols,
        dep_col=req.dep_col,
        history=history,
    )
    return result


@app.post("/api/llm-recommendations")
def get_llm_recommendations(req: IVAgentRequest):
    """Generate GPT-4o powered recommendations for all features."""
    from agents import llm_recommendations
    session = sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    iv_results = session.get("iv_results")
    if not iv_results:
        raise HTTPException(status_code=400, detail="Run IV analysis first.")
    recs = llm_recommendations(iv_results)
    return {"recommendations": recs}
