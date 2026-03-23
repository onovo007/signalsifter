"""
SignalSifter – AI Agent Layer
Dr. Amobi Andrew Onovo
"""
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import base64
import io
import traceback

from openai import OpenAI
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_openai import ChatOpenAI

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

EXPERTISE:
1. WoE/IV Methodology
2. Feature Selection based on IV thresholds
3. Feature Engineering for weak predictors
4. Data Quality diagnostics
5. Model building and interaction strategies

IV THRESHOLDS:
- IV > 0.5 : Very Strong (check for leakage)
- 0.3–0.5  : Strong (include)
- 0.1–0.3  : Moderate (engineer)
- 0.02–0.1 : Weak (quality check)
- < 0.02   : Not useful (exclude)

Answer the user concisely but thoroughly. Reference specific feature names and IV values.

User question: {question}
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": context}, {"role": "user", "content": question}],
            temperature=0.3,
            max_tokens=900,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Agent error: {str(e)}"


# ── General LangChain Data Agent ──────────────────────────────────────────────
def general_data_agent(question: str, df: pd.DataFrame, num_cols: list, dep_col: str) -> dict:
    if df is None or df.empty:
        return {"text": "No dataset loaded. Please upload a file first.", "plot_b64": None}

    try:
        df.columns = [c.strip().lower() for c in df.columns]
        llm = ChatOpenAI(temperature=0, model="gpt-4o")
        agent = create_pandas_dataframe_agent(
            llm=llm,
            df=df,
            verbose=False,
            allow_dangerous_code=True,
            handle_parsing_errors=True,
        )

        plt.close("all")
        prompt = f"""You are a skilled data scientist using Python pandas and matplotlib.
INSTRUCTIONS:
- When plotting, ALWAYS use plt.figure() and do NOT call plt.show()
- Use descriptive titles and axis labels
- Available columns: {', '.join(df.columns)}
Question: {question}"""

        result = agent.invoke({"input": prompt})
        text = result.get("output", str(result)) if isinstance(result, dict) else str(result)

        plot_b64 = None
        try:
            if plt.get_fignums():
                fig = plt.gcf()
                if fig and fig.get_axes():
                    fig.tight_layout()
                    buf = io.BytesIO()
                    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
                    buf.seek(0)
                    plot_b64 = base64.b64encode(buf.read()).decode()
                    plt.close("all")
        except Exception:
            pass

        return {"text": text, "plot_b64": plot_b64}

    except Exception as e:
        plt.close("all")
        return {"text": f"Agent error: {str(e)}\n\n{traceback.format_exc()[-600:]}", "plot_b64": None}
