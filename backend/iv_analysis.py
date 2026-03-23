"""
SignalSifter - IV/WoE Analysis Engine
Dr. Amobi Andrew Onovo
"""
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.utils
import json
from scipy import stats


# ── IV colour thresholds ────────────────────────────────────────────────────
def iv_color(iv: float) -> str:
    if iv > 0.5:
        return "#006400"
    if iv >= 0.3:
        return "#228B22"
    if iv >= 0.1:
        return "#FFA500"
    if iv >= 0.02:
        return "#FF4500"
    return "#A9A9A9"


def iv_label(iv: float) -> str:
    if iv > 0.5:
        return "Very Strong Predictor"
    if iv >= 0.3:
        return "Strong Predictor"
    if iv >= 0.1:
        return "Moderate Predictor"
    if iv >= 0.02:
        return "Weak Predictor"
    return "Not Useful"


# ── Gini & KS ───────────────────────────────────────────────────────────────
def calculate_gini(feature: pd.Series, target: pd.Series) -> float:
    try:
        from sklearn.metrics import roc_auc_score
        if feature.nunique() > 1:
            auc = roc_auc_score(target, feature)
            return round(2 * auc - 1, 4)
        return 0.0
    except Exception:
        return 0.0


def calculate_ks(feature: pd.Series, target: pd.Series) -> float:
    try:
        t0 = feature[target == 0]
        t1 = feature[target == 1]
        ks, _ = stats.ks_2samp(t0, t1)
        return round(ks, 4)
    except Exception:
        return 0.0


# ── WoE / IV per feature ────────────────────────────────────────────────────
def compute_woe_iv(df: pd.DataFrame, feature: str, target: str, bins: int = 5):
    tmp = df[[feature, target]].dropna().copy()

    if pd.api.types.is_numeric_dtype(tmp[feature]):
        try:
            tmp["__bin"], _ = pd.qcut(tmp[feature], q=bins, duplicates="drop", retbins=True)
        except Exception:
            tmp["__bin"] = pd.cut(tmp[feature], bins=bins, duplicates="drop")
        groups = tmp.groupby("__bin", observed=True)
    else:
        groups = tmp.groupby(feature, observed=True)

    total_event = tmp[target].sum()
    total_non = tmp.shape[0] - total_event

    records, iv = [], 0.0
    for bin_name, grp in groups:
        evt = grp[target].sum()
        non = grp.shape[0] - evt
        count = grp.shape[0]
        event_rate = evt / count if count > 0 else 0
        pct_evt = evt / total_event if total_event > 0 else 0
        pct_non = non / total_non if total_non > 0 else 0
        woe = np.log((pct_evt + 1e-10) / (pct_non + 1e-10))
        iv_contrib = (pct_evt - pct_non) * woe
        iv += iv_contrib
        records.append({
            "Bin": str(bin_name),
            "Count": int(count),
            "Events": int(evt),
            "Non-Events": int(non),
            "Event_Rate": round(event_rate, 4),
            "WoE": round(woe, 4),
            "IV_Contribution": round(iv_contrib, 4),
        })

    woe_df = pd.DataFrame(records)
    gini = calculate_gini(tmp[feature], tmp[target])
    ks = calculate_ks(tmp[feature], tmp[target])
    return round(iv, 4), woe_df, gini, ks


# ── Full analysis ────────────────────────────────────────────────────────────
def run_analysis(df: pd.DataFrame, target: str, features: list, exclude: list, bins: int):
    df_proc = df.drop(columns=exclude, errors="ignore")

    if target not in df_proc.columns:
        raise ValueError(f"Target column '{target}' not found in dataset.")

    summary_rows, woe_tables = [], {}
    for feat in features:
        if feat == target or feat not in df_proc.columns:
            continue
        iv_val, woe_df, gini, ks = compute_woe_iv(df_proc, feat, target, bins)
        summary_rows.append({"feature": feat, "IV": iv_val, "Gini": gini, "KS_Statistic": ks})
        woe_tables[feat] = woe_df

    iv_summary = pd.DataFrame(summary_rows).sort_values("IV", ascending=False).reset_index(drop=True)

    chart_json = build_iv_chart(iv_summary)
    recommendations = build_recommendations(iv_summary, woe_tables)
    top3_woe = build_top3_woe(woe_tables, iv_summary)
    metrics = build_metrics_summary(iv_summary)

    return {
        "summary": iv_summary.to_dict(orient="records"),
        "chart": chart_json,
        "recommendations": recommendations,
        "woe_top3": top3_woe.to_dict(orient="records"),
        "metrics": metrics,
        "woe_tables": {k: v.to_dict(orient="records") for k, v in woe_tables.items()},
        "target": target,
        "bins": bins,
        "n_features": len(iv_summary),
    }


# ── Plotly chart ─────────────────────────────────────────────────────────────
def build_iv_chart(iv_summary: pd.DataFrame) -> str:
    colors = [iv_color(v) for v in iv_summary["IV"]]
    hover = [
        f"<b>{r['feature']}</b><br>IV: {r['IV']:.4f}<br>Gini: {r['Gini']:.4f}<br>KS: {r['KS_Statistic']:.4f}<br><b>{iv_label(r['IV'])}</b>"
        for _, r in iv_summary.iterrows()
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=iv_summary["feature"],
        x=iv_summary["IV"],
        orientation="h",
        marker=dict(color=colors, line=dict(color="rgba(0,0,0,0.3)", width=1)),
        text=iv_summary["IV"].apply(lambda x: f"{x:.4f}"),
        textposition="outside",
        hovertext=hover,
        hoverinfo="text",
    ))
    fig.update_layout(
        title=dict(text="Feature IV Ranking", x=0.5, xanchor="center",
                   font=dict(size=18, color="#1a1a2e", family="Inter, Arial")),
        xaxis_title="Information Value (IV)",
        height=max(380, len(iv_summary) * 42),
        yaxis=dict(categoryorder="total ascending"),
        plot_bgcolor="rgba(248,250,252,0.9)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=12, family="Inter, Arial"),
        margin=dict(l=160, r=110, t=70, b=55),
        hoverlabel=dict(bgcolor="white", font_size=12),
    )
    for x_val, color in [(0.5, "green"), (0.3, "orange"), (0.1, "red")]:
        fig.add_vline(x=x_val, line_dash="dot", line_color=color, opacity=0.35)

    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)


# ── Recommendations ──────────────────────────────────────────────────────────
def build_recommendations(iv_summary: pd.DataFrame, woe_tables: dict) -> list:
    recs = []
    for _, row in iv_summary.iterrows():
        feat, iv, gini, ks = row["feature"], row["IV"], row["Gini"], row["KS_Statistic"]
        if iv > 0.5:
            action = "Prioritize — exceptional discriminatory power."
            steps = ["Check for potential data leakage", "Explore interactions with other strong predictors", "Review data collection methodology"]
        elif iv >= 0.3:
            action = "Include as core feature and explore interactions."
            steps = ["Test polynomial/interaction terms", "Optimize for ensemble model weighting", "Verify WoE monotonicity"]
        elif iv >= 0.1:
            action = "Feature engineering opportunity — moderate signal."
            steps = ["Try alternative binning strategies", "Derive domain-informed features", "Check for outlier dilution"]
        elif iv >= 0.02:
            action = "Investigate data quality before including."
            steps = ["Check for measurement errors", "Examine missing value patterns", "Try stratified sub-analysis"]
        else:
            action = "Exclude or redesign measurement."
            steps = ["Remove to reduce noise", "Re-evaluate data source", "Investigate theoretical relevance"]

        recs.append({
            "feature": feat, "iv": iv, "gini": gini, "ks": ks,
            "label": iv_label(iv), "color": iv_color(iv),
            "action": action, "steps": steps,
        })
    return recs


def build_top3_woe(woe_tables: dict, iv_summary: pd.DataFrame) -> pd.DataFrame:
    top3 = iv_summary.nlargest(3, "IV")["feature"].tolist()
    frames = []
    for feat in top3:
        if feat in woe_tables:
            tmp = woe_tables[feat].copy()
            tmp.insert(0, "Feature", feat)
            frames.append(tmp)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def build_metrics_summary(iv_summary: pd.DataFrame) -> dict:
    if iv_summary.empty:
        return {}
    return {
        "total": len(iv_summary),
        "very_strong": int((iv_summary["IV"] > 0.5).sum()),
        "strong": int(((iv_summary["IV"] >= 0.3) & (iv_summary["IV"] <= 0.5)).sum()),
        "moderate": int(((iv_summary["IV"] >= 0.1) & (iv_summary["IV"] < 0.3)).sum()),
        "weak": int(((iv_summary["IV"] >= 0.02) & (iv_summary["IV"] < 0.1)).sum()),
        "not_useful": int((iv_summary["IV"] < 0.02).sum()),
        "top_feature": iv_summary.iloc[0]["feature"],
        "top_iv": iv_summary.iloc[0]["IV"],
        "avg_iv": round(iv_summary["IV"].mean(), 4),
        "avg_gini": round(iv_summary["Gini"].mean(), 4),
    }
