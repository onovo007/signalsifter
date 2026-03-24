"""
SignalSifter – AI Agent Layer (v2.1)
Dr. Amobi Andrew Onovo
Upgrades: Plotly charts · Conversation memory · Python + SQL code generation
"""
import os
import re
import json
import traceback
import sys
import pandas as pd
import numpy as np
import plotly
import plotly.graph_objects as go
import plotly.express as px
from io import StringIO
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── IV-Aware Expert Agent ─────────────────────────────────────────────────────
def iv_expert_agent(question: str, iv_results: dict) -> str:
    if not iv_results:
        return "Please run an IV analysis first before asking questions."

    summary_str = pd.DataFrame(iv_results["summary"]).to_string()
    context = f"""
You are an expert data scientist specialising in Weight of Evidence (WoE) and Information Value (IV) analysis.

CURRENT ANALYSIS:
Target Variable: {iv_results.get('target', 'N/A')}
Features Analysed: {iv_results.get('n_features', 0)}
Binning Strategy: {iv_results.get('bins', 5)} bins

IV RESULTS:
{summary_str}

IV THRESHOLDS:
- IV > 0.5 : Very Strong (check for leakage)
- 0.3-0.5  : Strong (include)
- 0.1-0.3  : Moderate (engineer)
- 0.02-0.1 : Weak (quality check)
- < 0.02   : Not useful (exclude)

Answer concisely but thoroughly. Reference specific feature names and IV values.

User question: {question}
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": context},
                      {"role": "user", "content": question}],
            temperature=0.3,
            max_tokens=900,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Agent error: {str(e)}"


# ── System prompt for General Agent ─────────────────────────────────────────
SYSTEM_PROMPT = """You are an elite data scientist and Python/SQL expert with deep expertise in:
- Advanced statistical analysis and exploratory data analysis (EDA)
- Plotly for premium interactive visualisations (ALWAYS use Plotly, never matplotlib)
- Pandas, NumPy, SciPy for data manipulation and statistical tests
- SQL query generation and optimisation
- Machine learning with scikit-learn
- Writing clear, production-quality, well-commented Python code

CRITICAL RULES:
1. ALWAYS use Plotly for any chart, plot, or visualisation. Never use matplotlib or seaborn.
2. When generating a Plotly chart, the LAST line of the code block MUST be:
   print("PLOTLY_JSON:" + fig.to_json())
3. Wrap Python code in ```python ... ``` blocks
4. Wrap SQL code in ```sql ... ``` blocks
5. Always explain what the code does clearly before showing it
6. The dataframe is pre-loaded as `df` — never read from files
7. For SQL queries, assume the dataframe is a table called `data`
8. Reference conversation history to answer follow-up questions in context

PLOTLY STYLE (always apply these):
- template="plotly_white"
- Add meaningful title, axis labels, and hover tooltips
- Use px.colors.qualitative.Set2 for categorical color sequences
- Use color_continuous_scale="Teal" for heatmaps/continuous
- Always include: fig.update_layout(height=500, font=dict(family="Inter, Arial", size=13))
- Add fig.update_traces(marker=dict(line=dict(width=0.5, color="white"))) for bar/scatter
"""


# ── General Data Science Agent ────────────────────────────────────────────────
def general_data_agent(question: str, df: pd.DataFrame,
                       cat_cols: list = None, num_cols: list = None,
                       dep_col: str = None, history: list = None) -> dict:
    """
    Enhanced agent with Plotly charts, conversation memory, Python + SQL generation.
    history: list of {"role": "user"|"assistant", "content": str}
    """
    if df is None or df.empty:
        return {"text": "No dataset loaded. Please upload a file first.",
                "plotly_json": None, "code": None}

    df_info = _build_df_context(df, cat_cols or [], num_cols or [], dep_col)

    messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n\n" + df_info}]

    # Include last 10 conversation turns for memory
    if history:
        for turn in history[-10:]:
            messages.append({"role": turn["role"], "content": turn["content"]})

    messages.append({"role": "user", "content": question})

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.2,
            max_tokens=2500,
        )
        reply = response.choices[0].message.content

        # Extract Python code blocks and try to execute for Plotly output
        plotly_json = None
        code_blocks = _extract_code_blocks(reply, "python")

        if code_blocks:
            plotly_json = _execute_plotly_code(code_blocks[0], df)

        return {
            "text": reply,
            "plotly_json": plotly_json,
            "code": code_blocks[0] if code_blocks else None,
        }

    except Exception as e:
        return {
            "text": f"Agent error: {str(e)}\n{traceback.format_exc()[-400:]}",
            "plotly_json": None,
            "code": None,
        }


def _build_df_context(df: pd.DataFrame, cat_cols: list, num_cols: list, dep_col: str) -> str:
    """Build a rich dataframe context string for the LLM."""
    shape = df.shape
    dtypes = df.dtypes.to_string()
    sample = df.head(3).to_string()
    nulls = df.isnull().sum()
    nulls_str = nulls[nulls > 0].to_string() if nulls.any() else "None"

    numeric_df = df.select_dtypes(include=[np.number])
    stats = numeric_df.describe().round(3).to_string() if not numeric_df.empty else "N/A"

    selected_cat = f"User-selected categorical columns: {cat_cols}" if cat_cols else ""
    selected_num = f"User-selected numerical columns: {num_cols}" if num_cols else ""
    selected_dep = f"Dependent variable: {dep_col}" if dep_col else ""

    return f"""
DATASET CONTEXT:
Shape: {shape[0]} rows x {shape[1]} columns
Columns & dtypes:
{dtypes}

Missing values: {nulls_str}

Descriptive statistics:
{stats}

Sample rows:
{sample}

{selected_cat}
{selected_num}
{selected_dep}

The dataframe is available as `df` in your code.
"""


def _extract_code_blocks(text: str, lang: str = "python") -> list:
    """Extract fenced code blocks of a given language."""
    pattern = rf"```{lang}\s*(.*?)```"
    return re.findall(pattern, text, re.DOTALL)


def _execute_plotly_code(code: str, df: pd.DataFrame):
    """
    Execute Python code in a sandboxed namespace.
    Captures Plotly figure JSON via print marker or `fig` variable.
    """
    namespace = {
        "df": df.copy(),
        "pd": pd,
        "np": np,
        "go": go,
        "px": px,
        "json": json,
    }

    stdout_capture = StringIO()
    old_stdout = sys.stdout
    sys.stdout = stdout_capture

    try:
        exec(code, namespace)  # nosec
    except Exception:
        sys.stdout = old_stdout
        return None
    finally:
        sys.stdout = old_stdout

    output = stdout_capture.getvalue()

    # Method 1: look for PLOTLY_JSON: marker in stdout
    for line in output.splitlines():
        if line.startswith("PLOTLY_JSON:"):
            return line[len("PLOTLY_JSON:"):]

    # Method 2: look for `fig` variable in namespace
    fig = namespace.get("fig")
    if fig is not None and hasattr(fig, "to_json"):
        return fig.to_json()

    return None


# ── LLM-Powered Feature Recommendations ──────────────────────────────────────
def llm_recommendations(iv_results: dict) -> list:
    """
    Generate rich, expert recommendations for each feature using GPT-4o.
    Returns a list of dicts: {feature, iv, gini, ks, label, color, action, steps, narrative}
    """
    if not iv_results or not iv_results.get("summary"):
        return []

    summary_df = pd.DataFrame(iv_results["summary"])
    summary_str = summary_df.to_string(index=False)
    target = iv_results.get("target", "target")

    prompt = f"""You are a senior data scientist expert in WoE/IV analysis for binary classification models.

DATASET TARGET: {target}

IV ANALYSIS RESULTS:
{summary_str}

For EACH feature listed above, generate expert recommendations. Respond in valid JSON only — an array of objects with this exact structure:
[
  {{
    "feature": "feature_name",
    "action": "One-sentence primary action",
    "narrative": "2-3 sentences of expert insight about this specific feature's IV, Gini, and KS patterns and what they imply about the data and target relationship",
    "steps": ["Specific step 1", "Specific step 2", "Specific step 3"]
  }}
]

Be specific to the actual feature names and values. Do not be generic. Reference the actual IV, Gini, KS numbers in your narrative. Return ONLY the JSON array, no preamble."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2500,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        parsed = json.loads(raw)
        # Handle both {"recommendations": [...]} and plain [...]
        recs_raw = parsed if isinstance(parsed, list) else parsed.get("recommendations", list(parsed.values())[0])

        # Merge with IV/colour data
        iv_map = {r["feature"]: r for r in iv_results["summary"]}
        results = []
        for rec in recs_raw:
            feat = rec.get("feature", "")
            iv_row = iv_map.get(feat, {})
            iv = iv_row.get("IV", 0)
            results.append({
                "feature": feat,
                "iv": iv,
                "gini": iv_row.get("Gini", 0),
                "ks":   iv_row.get("KS_Statistic", 0),
                "label": _iv_label(iv),
                "color": _iv_color(iv),
                "action": rec.get("action", ""),
                "narrative": rec.get("narrative", ""),
                "steps": rec.get("steps", []),
            })
        return results
    except Exception as e:
        # Fallback to static recommendations
        return []


def _iv_color(iv: float) -> str:
    if iv > 0.5:  return "#006400"
    if iv >= 0.3: return "#228B22"
    if iv >= 0.1: return "#d97706"
    if iv >= 0.02:return "#dc2626"
    return "#6b7280"


def _iv_label(iv: float) -> str:
    if iv > 0.5:  return "Very Strong"
    if iv >= 0.3: return "Strong"
    if iv >= 0.1: return "Moderate"
    if iv >= 0.02:return "Weak"
    return "Not Useful"
