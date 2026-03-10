import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
import plotly.express as px
import json
import os
import time
from datetime import datetime

# ==========================================
# PAGE CONFIG & CSS
# ==========================================
st.set_page_config(page_title="Kylas Intelligence", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; background-color: #0d0f12; color: #e2e8f0; }
.stApp { background-color: #0d0f12; }
[data-testid="stSidebar"] { background-color: #111418 !important; border-right: 1px solid #1e2530; }
.intel-card { background: #151a22; border: 1px solid #1e2b3c; border-radius: 8px; padding: 20px 24px; margin-bottom: 16px; }
.metric-row { display: flex; gap: 12px; margin-bottom: 20px; }
.metric-box { flex: 1; background: #151a22; border: 1px solid #1e2b3c; border-radius: 6px; padding: 16px; text-align: center; }
.metric-box .val { font-family: 'IBM Plex Mono', monospace; font-size: 28px; font-weight: 600; color: #2a7aff; }
.metric-box .lbl { font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 1px; }
h1, h2, h3 { font-family: 'IBM Plex Mono', monospace !important; }
.stButton > button { background: #2a7aff !important; color: white !important; font-family: 'IBM Plex Mono', monospace !important; border-radius: 4px !important; width: 100%; }
.tag { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 11px; font-family: 'IBM Plex Mono', monospace; font-weight: 600; }
.tag-blue  { background: #1a3a6b; color: #60a5fa; }
.divider { border: none; border-top: 1px solid #1e2530; margin: 20px 0; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# HISTORY LOGIC
# ==========================================
HISTORY_FILE = "crm_intelligence_history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_to_history(entry: dict):
    history = load_history()
    history.insert(0, entry)
    history = history[:100]
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

# ==========================================
# KYLAS CACHE & FLATTENER LOGIC
# ==========================================
ENTITY_CONFIG = {
    "Leads": {"endpoint": "/search/lead"}, "Contacts": {"endpoint": "/search/contact"},
    "Companies": {"endpoint": "/search/company"}, "Deals": {"endpoint": "/search/deal"},
}

def load_from_cache(entity: str) -> list:
    import sqlite3
    DB_FILE = "kylas_cache.db"
    if not os.path.exists(DB_FILE): return []
    try:
        conn = sqlite3.connect(DB_FILE)
        rows = conn.execute("SELECT data FROM records WHERE entity=?", (entity,)).fetchall()
        conn.close()
        return [json.loads(row[0]) for row in rows]
    except: return []

def flatten_records(records: list) -> pd.DataFrame:
    flat = []
    for r in records:
        d = {
            "ID": r.get("id"),
            "Name": r.get("name") or f"{r.get('firstName','')} {r.get('lastName','')}".strip() or None,
            "Industry": (r.get("industry") or {}).get("name") if isinstance(r.get("industry"), dict) else r.get("industry"),
            "Employee Size": (r.get("numberOfEmployees") or {}).get("name") if isinstance(r.get("numberOfEmployees"), dict) else r.get("numberOfEmployees"),
        }
        for k, v in (r.get("customFieldValues") or {}).items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                d[k] = ", ".join(i.get("name","") for i in v if i.get("name"))
            elif isinstance(v, dict): d[k] = v.get("name") or v.get("value")
            else: d[k] = v
        flat.append(d)
    df = pd.DataFrame(flat)
    df.dropna(axis=1, how="all", inplace=True)
    return df

# ==========================================
# GEMINI AI INTELLIGENCE
# ==========================================
def call_gemini(api_key: str, entity: str, field: str, raw_counts: dict) -> dict | None:
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash', generation_config={"response_mime_type": "application/json"})
        prompt = f"""
        Entity: {entity} | Field: {field} | Counts: {json.dumps(raw_counts)}
        1. Group raw text values into clean, standardized categories.
        2. Recommend chart type: 'Bar Chart', 'Pie Chart', or 'Donut Chart'.
        Return JSON: {{"graph_type": "Bar Chart", "mapping": {{"raw_val": "Standard Category"}}, "insight": "Short insight."}}
        """
        res = model.generate_content(prompt)
        return json.loads(res.text)
    except Exception as e:
        st.error(f"Gemini error: {e}")
        return None

# ==========================================
# CHART RENDERER
# ==========================================
def render_chart(viz_df: pd.DataFrame, field: str, graph_type: str):
    CHART_COLORS = ["#2a7aff","#06b6d4","#8b5cf6","#f59e0b","#10b981","#ef4444","#ec4899","#84cc16"]
    fig = None
    if "Bar" in graph_type:
        fig = px.bar(viz_df, x=field, y="Count", color=field, color_discrete_sequence=CHART_COLORS, template="plotly_dark")
        fig.update_layout(paper_bgcolor="#151a22", plot_bgcolor="#151a22", showlegend=False)
    elif "Pie" in graph_type or "Donut" in graph_type:
        hole = 0.45 if "Donut" in graph_type else 0
        fig = px.pie(viz_df, values="Count", names=field, color_discrete_sequence=CHART_COLORS, hole=hole, template="plotly_dark")
        fig.update_layout(paper_bgcolor="#151a22", plot_bgcolor="#151a22")
    if fig: st.plotly_chart(fig, use_container_width=True)

# ==========================================
# SESSION STATE INIT
# ==========================================
for key, default in [
    ("kylas_key", ""), ("gemini_key", ""), ("keys_set", False), 
    ("df", None), ("filtered_df", None), ("entity", None), 
    ("analysis", None), ("analyzed_field", None),
]:
    if key not in st.session_state: st.session_state[key] = default

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.markdown("### ⚡ KYLAS INTELLIGENCE")
    
    st.markdown("**API CONFIGURATION**")
    kylas_input  = st.text_input("Kylas API Key", type="password", value=st.session_state.kylas_key)
    gemini_input = st.text_input("Gemini API Key", type="password", value=st.session_state.gemini_key)
    if st.button("Save Keys"):
        st.session_state.kylas_key, st.session_state.gemini_key, st.session_state.keys_set = kylas_input, gemini_input, True
        st.success("✅ Keys saved")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown("**DATA SOURCE**")
    entity = st.selectbox("Module", list(ENTITY_CONFIG.keys()))

    if st.button("⚡ Load Local Cache DB"):
        records = load_from_cache(entity)
        if records:
            st.session_state.df = flatten_records(records)
            st.session_state.filtered_df = st.session_state.df.copy() # Initial sync
            st.session_state.entity = entity
            st.session_state.analysis = None
            st.success(f"✅ {len(records):,} records loaded")
        else: st.error("Cache empty or DB not found.")

    # ── SLICER LOGIC ────────────────────
    if st.session_state.df is not None and st.session_state.entity == entity:
        current_df = st.session_state.df.copy()
        exclude = {"ID", "Name", "Emails", "Phones", "Created At", "Amount"}
        
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        st.markdown("**✂️ DATA SLICER (FILTER POOL)**")
        
        filter_options = [c for c in current_df.columns if c not in exclude and current_df[c].nunique() < 50]
        selected_filters = st.multiselect("Add Filters:", filter_options)
        
        for col in selected_filters:
            unique_vals = current_df[col].dropna().unique().tolist()
            chosen_vals = st.multiselect(f"Select {col}:", unique_vals, default=unique_vals)
            current_df = current_df[current_df[col].isin(chosen_vals)]
            
        st.session_state.filtered_df = current_df
        st.markdown(f"<div style='background:#14362b;padding:8px;border-radius:4px;text-align:center;color:#4ade80;'>🎯 POOL SIZE: {len(current_df):,}</div>", unsafe_allow_html=True)

        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        st.markdown("**🧠 AI ANALYSIS**")
        analyzable = [c for c in current_df.columns if c not in exclude and current_df[c].nunique() >= 1]
        
        if analyzable and len(current_df) > 0:
            field = st.selectbox("Field to Analyze", analyzable)
            if st.button("Run Gemini Analysis"):
                raw_counts = {str(k): int(v) for k, v in current_df[field].value_counts().to_dict().items()}
                with st.spinner("🧠 Gemini analyzing sliced pool..."):
                    result = call_gemini(st.session_state.gemini_key, entity, field, raw_counts)
                if result:
                    st.session_state.analysis, st.session_state.analyzed_field = result, field
                    entry = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "entity": entity, "field": field, "graph_type": result.get("graph_type"), "mapping": result.get("mapping", {}), "raw_counts": raw_counts}
                    save_to_history(entry)
                    st.success("✅ Analysis complete")

# ==========================================
# MAIN AREA
# ==========================================
tab1, tab2, tab3 = st.tabs(["📊 ANALYSIS", "🗃 DATA TABLE", "🕘 HISTORY"])

with tab1:
    if st.session_state.analysis and st.session_state.filtered_df is not None:
        intel, field, df, entity = st.session_state.analysis, st.session_state.analyzed_field, st.session_state.filtered_df, st.session_state.entity
        df["_std"] = df[field].astype(str).map(intel.get("mapping", {})).fillna("Other")
        viz_df = df["_std"].value_counts().reset_index()
        viz_df.columns = [field, "Count"]

        st.markdown(f"<div class='intel-card'><h3>{entity} → {field}</h3><span class='tag tag-blue'>{intel.get('graph_type','')}</span></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='metric-row'><div class='metric-box'><div class='val'>{len(df):,}</div><div class='lbl'>Pool Size</div></div></div>", unsafe_allow_html=True)
        render_chart(viz_df, field, intel.get("graph_type","Bar Chart"))
        with st.expander("View AI Mapping"): st.json(intel)
    else: st.info("Load data and run analysis from sidebar.")

with tab2:
    if st.session_state.filtered_df is not None:
        df = st.session_state.filtered_df
        st.markdown(f"**{st.session_state.entity} (Filtered)** — {len(df):,} records")
        st.dataframe(df, use_container_width=True, height=500)
        st.download_button("⬇ Download Filtered CSV", df.to_csv(index=False).encode("utf-8"), f"{st.session_state.entity}_pool.csv", "text/csv")

with tab3:
    history = load_history()
    if history:
        for entry in history:
            with st.expander(f"[{entry['timestamp']}] {entry['entity']} → {entry['field']}"):
                st.json(entry)
    else: st.info("No history yet.")
