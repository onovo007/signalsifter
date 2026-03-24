"""
SignalSifter – AI Agent Layer (v2.2)
Dr. Amobi Andrew Onovo
Fixes: statsmodels execution · robust LLM recs · weak-predictor-only recs
"""
import os, re, json, traceback, sys
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from io import StringIO
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ═══════════════════════════════════════════════════════════════════════════════
# IV-AWARE EXPERT AGENT
# ═══════════════════════════════════════════════════════════════════════════════
def iv_expert_agent(question: str, iv_results: dict) -> str:
    if not iv_results:
        return "Please run an IV analysis first before asking questions."

    summary_str = pd.DataFrame(iv_results["summary"]).to_string()
    context = f"""
You are an expert data scientist specialising in Weight of Evidence (WoE) and
Information Value (IV) analysis for binary classification.

CURRENT ANALYSIS:
Target Variable : {iv_results.get('target', 'N/A')}
Features        : {iv_results.get('n_features', 0)}
Bins            : {iv_results.get('bins', 5)}

IV RESULTS:
{summary_str}

IV THRESHOLDS:
- IV > 0.5  : Very Strong (check for data leakage)
- 0.3–0.5   : Strong     (include in model)
- 0.1–0.3   : Moderate   (feature engineer)
- 0.02–0.1  : Weak       (data quality check)
- < 0.02    : Not useful (exclude)

Answer concisely but thoroughly. Reference specific feature names and IV values.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": context},
                      {"role": "user", "content": question}],
            temperature=0.3, max_tokens=900,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Agent error: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# GENERAL DATA SCIENCE AGENT
# ═══════════════════════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """You are an elite data scientist and Python expert.

MANDATORY EXECUTION RULES — follow these exactly every time:

1. When asked to run, compute, fit, or analyse anything:
   - Write a COMPLETE, SELF-CONTAINED Python code block
   - The code WILL be executed server-side — do not just describe it
   - All imports must be inside the code block (statsmodels, scipy, sklearn, etc.)
   - Data is in `df` — never read files

2. For ALL statistical tables (regression, ANOVA, summary stats):
   - Build a Plotly go.Table figure showing the results
   - End the code block with: print("PLOTLY_JSON:" + fig.to_json())

3. For ALL charts and visualisations:
   - Use ONLY Plotly (never matplotlib or seaborn)
   - End the code block with: print("PLOTLY_JSON:" + fig.to_json())

4. PLOTLY TABLE style — use this EXACT pattern, no deviations:

   header=dict(
       values=["Col1", "Col2"],
       fill_color="#006666",
       font_color="white",
       font_size=13,
       align="center",
   ),
   cells=dict(
       values=[col1_data, col2_data],
       fill_color=[["#0a1628","#0f2040"] * (len(data)//2 + 1)][:1] * len(columns),
       font_color="#e8f0ff",
       font_size=12,
       align="left",
   )
   fig.update_layout(height=500, paper_bgcolor="rgba(255,255,255,0.04)",
                     font=dict(family="DM Sans, Arial", size=12))

   CRITICAL TABLE RULES:
   - NEVER use font=dict(...) inside header or cells — use font_color= and font_size= directly
   - NEVER use bold=True anywhere in any font specification
   - For alternating row colors use: fill_color=[["#0a1628","#0f2040"]*(n//2+1)][:n] as a list

5. PLOTLY CHART style — copy this update_layout block EXACTLY every time:
   fig.update_layout(
       template="plotly_dark",
       paper_bgcolor="rgba(255,255,255,0.04)",
       plot_bgcolor="rgba(255,255,255,0.07)",
       font=dict(color="#a0b4d0", family="DM Sans, Arial", size=12),
       xaxis=dict(gridcolor="rgba(255,255,255,0.1)", zerolinecolor="rgba(255,255,255,0.15)"),
       yaxis=dict(gridcolor="rgba(255,255,255,0.1)", zerolinecolor="rgba(255,255,255,0.15)"),
       height=500,
   )
   NEVER put gridcolor directly in update_layout — always inside xaxis/yaxis dicts.
   NEVER use font_color as a top-level update_layout key.

6. Wrap Python in ```python ... ``` blocks.
   Wrap SQL in ```sql ... ``` blocks.

7. Keep explanations concise. Put them BEFORE the code block, not after.

8. STATELESS EXECUTION — the most important rule for follow-up questions:
   Each code block runs in a FRESH Python environment. Variables from previous
   turns DO NOT exist. `result`, `model`, `summary`, `fig` — all gone.
   
   On ANY follow-up (e.g. "show significant variables", "plot odds ratios",
   "interpret the results"):
   - Re-run the COMPLETE pipeline from scratch in one self-contained block
   - Re-import libraries, re-fit the model, re-extract results, THEN show new output
   - Use conversation history ONLY to understand intent — not as live code state
   
   Example: if user says "now show odds ratios", your code must:
   1. Re-import statsmodels, re-fit logistic regression
   2. Compute odds ratios = np.exp(result.params)
   3. Build and display the Plotly table/chart
   All in one code block.
"""


def general_data_agent(question: str, df: pd.DataFrame,
                       cat_cols: list = None, num_cols: list = None,
                       dep_col: str = None, history: list = None) -> dict:
    if df is None or df.empty:
        return {"text": "No dataset loaded.", "plotly_json": None, "code": None}

    df_info = _build_df_context(df, cat_cols or [], num_cols or [], dep_col)
    messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n\n" + df_info}]
    if history:
        for turn in history[-10:]:
            messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": question})

    try:
        response = client.chat.completions.create(
            model="gpt-4o", messages=messages,
            temperature=0.15, max_tokens=3000,
        )
        reply = response.choices[0].message.content
        code_blocks = _extract_code_blocks(reply, "python")
        plotly_json = _execute_plotly_code(code_blocks[0], df) if code_blocks else None
        return {"text": reply, "plotly_json": plotly_json,
                "code": code_blocks[0] if code_blocks else None}
    except Exception as e:
        return {"text": f"Agent error: {e}\n{traceback.format_exc()[-400:]}",
                "plotly_json": None, "code": None}


def _build_df_context(df, cat_cols, num_cols, dep_col):
    shape   = df.shape
    dtypes  = df.dtypes.to_string()
    sample  = df.head(3).to_string()
    nulls   = df.isnull().sum()
    nulls_s = nulls[nulls > 0].to_string() if nulls.any() else "None"
    num_df  = df.select_dtypes(include=[np.number])
    stats   = num_df.describe().round(3).to_string() if not num_df.empty else "N/A"
    return f"""
DATASET: {shape[0]} rows × {shape[1]} columns
Dtypes:
{dtypes}

Missing: {nulls_s}

Stats:
{stats}

Sample:
{sample}

Selected categorical: {cat_cols or 'none specified'}
Selected numerical  : {num_cols or 'none specified'}
Dependent variable  : {dep_col or 'none specified'}

Dataframe available as `df`.
"""


def _extract_code_blocks(text, lang="python"):
    return re.findall(rf"```{lang}\s*(.*?)```", text, re.DOTALL)



def _sanitise_code(code):
    """Remove invalid Plotly font kwargs GPT-4o sometimes emits."""
    import re as r
    code = r.sub(r",?\s*bold\s*=\s*(?:True|False)", "", code)
    return code


def _execute_plotly_code(code: str, df: pd.DataFrame):
    code = _sanitise_code(code)
    """Execute code server-side. statsmodels, scipy, sklearn all available."""
    try:
        import statsmodels.api as sm
        import statsmodels.formula.api as smf
        from scipy import stats as scipy_stats
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import roc_auc_score, classification_report
    except ImportError:
        pass  # best-effort imports

    namespace = {
        "df": df.copy(), "pd": pd, "np": np,
        "go": go, "px": px, "json": json,
    }
    # Inject optional libraries if available
    for lib_name, lib_alias in [
        ("statsmodels.api", "sm"),
        ("statsmodels.formula.api", "smf"),
        ("scipy.stats", "scipy_stats"),
        ("sklearn.linear_model", "linear_model"),
        ("sklearn.metrics", "metrics"),
        ("sklearn.preprocessing", "preprocessing"),
    ]:
        try:
            import importlib
            namespace[lib_alias] = importlib.import_module(lib_name)
        except Exception:
            pass

    stdout_cap = StringIO()
    old_out = sys.stdout
    sys.stdout = stdout_cap
    try:
        exec(code, namespace)          # nosec
    except Exception as exc:
        sys.stdout = old_out
        # Return a Plotly error table so user sees what went wrong
        err_msg = traceback.format_exc()
        fig = go.Figure(go.Table(
            header=dict(values=["Execution Error"],
                        fill_color="#7f1d1d",
                        font_color="white", font_size=13, align="left"),
            cells=dict(values=[[err_msg]],
                       fill_color="#1c0a0a",
                       font_color="#fca5a5", font_size=11, align="left"),
        ))
        fig.update_layout(height=300, paper_bgcolor="rgba(255,255,255,0.04)")
        return fig.to_json()
    finally:
        sys.stdout = old_out

    output = stdout_cap.getvalue()

    # Priority 1 — PLOTLY_JSON: marker in stdout
    for line in output.splitlines():
        if line.startswith("PLOTLY_JSON:"):
            return line[len("PLOTLY_JSON:"):]

    # Priority 2 — `fig` variable in namespace
    fig = namespace.get("fig")
    if fig is not None and hasattr(fig, "to_json"):
        return fig.to_json()

    # Priority 3 — if there's printed text output (e.g. a dataframe),
    # wrap it in a Plotly table so it renders visually
    if output.strip():
        lines = [l for l in output.strip().splitlines() if l.strip()]
        fig = go.Figure(go.Table(
            header=dict(
                values=["Output"],
                fill_color="#006666",
                font_color="white",
                font_size=12,
                align="left",
            ),
            cells=dict(
                values=[lines],
                fill_color="#0a1628",
                font_color="#e8f0ff",
                font_size=11,
                align="left",
            ),
        ))
        fig.update_layout(
            height=max(300, len(lines) * 30 + 80),
            paper_bgcolor="rgba(255,255,255,0.04)",
            margin=dict(l=10, r=10, t=10, b=10)
        )
        return fig.to_json()

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# LLM-POWERED FEATURE RECOMMENDATIONS
# Only targets WEAK + MODERATE predictors (IV < 0.3) — actionable focus
# ═══════════════════════════════════════════════════════════════════════════════
def llm_recommendations(iv_results: dict) -> list:
    if not iv_results or not iv_results.get("summary"):
        return []

    summary_df = pd.DataFrame(iv_results["summary"])
    target = iv_results.get("target", "target")

    # ── Filter to features needing attention (IV < 0.3) ──────────────────────
    needs_attention = summary_df[summary_df["IV"] < 0.3].copy()
    strong_features = summary_df[summary_df["IV"] >= 0.3].copy()

    if needs_attention.empty:
        # All features are strong — brief note, no deep recs needed
        needs_attention = summary_df.copy()

    weak_str   = needs_attention.to_string(index=False)
    strong_str = strong_features[["feature","IV"]].to_string(index=False) if not strong_features.empty else "None"

    prompt = f"""You are a senior data scientist specialising in WoE/IV analysis.

TARGET VARIABLE: {target}

STRONG PREDICTORS (IV ≥ 0.3) — already good, no action needed:
{strong_str}

FEATURES NEEDING ATTENTION (IV < 0.3) — focus your recommendations here:
{weak_str}

Generate expert, specific recommendations ONLY for the features needing attention.
Each recommendation must reference the actual IV, Gini, and KS values and explain
what they reveal about the predictor-target relationship.

Respond with a JSON object in this exact format:
{{
  "recommendations": [
    {{
      "feature": "exact_feature_name",
      "action": "One clear sentence on what to do",
      "narrative": "2-3 sentences citing the actual IV/Gini/KS values and their meaning",
      "steps": ["Concrete step 1", "Concrete step 2", "Concrete step 3"]
    }}
  ]
}}

Be specific. Do not be generic. Do not include strong predictors."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.25,
            max_tokens=2500,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        parsed = json.loads(raw)

        # Always expect {"recommendations": [...]} thanks to the explicit prompt
        recs_raw = parsed.get("recommendations", [])
        if not recs_raw and isinstance(parsed, dict):
            # Fallback: grab the first list value in the dict
            for v in parsed.values():
                if isinstance(v, list):
                    recs_raw = v
                    break

        iv_map = {r["feature"]: r for r in iv_results["summary"]}
        results = []
        for rec in recs_raw:
            feat = rec.get("feature", "")
            iv_row = iv_map.get(feat, {})
            iv = float(iv_row.get("IV", 0))
            results.append({
                "feature":   feat,
                "iv":        iv,
                "gini":      iv_row.get("Gini", 0),
                "ks":        iv_row.get("KS_Statistic", 0),
                "label":     _iv_label(iv),
                "color":     _iv_color(iv),
                "action":    rec.get("action", ""),
                "narrative": rec.get("narrative", ""),
                "steps":     rec.get("steps", []),
            })
        return results

    except Exception as e:
        print(f"LLM recommendations error: {e}\n{traceback.format_exc()}")
        return []


# ── Colour / label helpers ────────────────────────────────────────────────────
def _iv_color(iv: float) -> str:
    if iv > 0.5:   return "#006400"
    if iv >= 0.3:  return "#228B22"
    if iv >= 0.1:  return "#d97706"
    if iv >= 0.02: return "#dc2626"
    return "#6b7280"

def _iv_label(iv: float) -> str:
    if iv > 0.5:   return "Very Strong"
    if iv >= 0.3:  return "Strong"
    if iv >= 0.1:  return "Moderate"
    if iv >= 0.02: return "Weak"
    return "Not Useful"
