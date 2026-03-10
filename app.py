import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import time
from datetime import datetime

# ==========================================
# PAGE CONFIG
# ==========================================
st.set_page_config(
    page_title="Kylas Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# CUSTOM CSS — dark industrial aesthetic
# ==========================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    background-color: #0d0f12;
    color: #e2e8f0;
}

/* Main background */
.stApp { background-color: #0d0f12; }

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #111418 !important;
    border-right: 1px solid #1e2530;
}

/* Cards */
.intel-card {
    background: #151a22;
    border: 1px solid #1e2b3c;
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 16px;
}

.intel-card:hover { border-color: #2a7aff; transition: border-color 0.2s; }

/* Metric boxes */
.metric-row { display: flex; gap: 12px; margin-bottom: 20px; }
.metric-box {
    flex: 1;
    background: #151a22;
    border: 1px solid #1e2b3c;
    border-radius: 6px;
    padding: 16px;
    text-align: center;
}
.metric-box .val {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 28px;
    font-weight: 600;
    color: #2a7aff;
}
.metric-box .lbl { font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 1px; }

/* History item */
.history-item {
    background: #111418;
    border: 1px solid #1e2530;
    border-left: 3px solid #2a7aff;
    border-radius: 4px;
    padding: 12px 16px;
    margin-bottom: 8px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
}

/* Headings */
h1, h2, h3 { font-family: 'IBM Plex Mono', monospace !important; }
h1 { color: #f1f5f9 !important; font-size: 22px !important; letter-spacing: -0.5px; }

/* Buttons */
.stButton > button {
    background: #2a7aff !important;
    color: white !important;
    border: none !important;
    border-radius: 4px !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    padding: 8px 20px !important;
    width: 100%;
}
.stButton > button:hover { background: #1a6aef !important; }

/* Input fields */
.stTextInput input, .stSelectbox select {
    background: #151a22 !important;
    border: 1px solid #1e2b3c !important;
    border-radius: 4px !important;
    color: #e2e8f0 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 13px !important;
}

/* Status tag */
.tag {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-family: 'IBM Plex Mono', monospace;
    font-weight: 600;
}
.tag-blue  { background: #1a3a6b; color: #60a5fa; }
.tag-green { background: #14362b; color: #4ade80; }
.tag-amber { background: #3b2a0a; color: #fbbf24; }

/* Divider */
.divider { border: none; border-top: 1px solid #1e2530; margin: 20px 0; }

/* Hide streamlit branding */
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# HISTORY FILE
# ==========================================
HISTORY_FILE = "crm_intelligence_history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_to_history(entry: dict):
    history = load_history()
    history.insert(0, entry)      # newest first
    history = history[:100]       # cap at 100 entries
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


# ==========================================
# KYLAS API LAYER (real, paginated)
# ==========================================
KYLAS_BASE = "https://api.kylas.io/v1"

ENTITY_CONFIG = {
    "Leads":     {"endpoint": "/search/lead",    "fields": ["id","name","emails","phoneNumbers","customFieldValues","numberOfEmployees","industry","pipelineStage","ownedBy","createdAt"]},
    "Contacts":  {"endpoint": "/search/contact", "fields": ["id","name","emails","phoneNumbers","customFieldValues","designation","ownedBy","createdAt"]},
    "Companies": {"endpoint": "/search/company", "fields": ["id","name","numberOfEmployees","industry","customFieldValues","annualRevenue","ownedBy","createdAt"]},
    "Deals":     {"endpoint": "/search/deal",    "fields": ["id","name","amount","pipeline","pipelineStage","customFieldValues","ownedBy","createdAt"]},
}

def kylas_fetch_all(api_key: str, entity: str) -> list:
    """Fetches ALL records for an entity using paginated POST search."""
    cfg     = ENTITY_CONFIG[entity]
    headers = {"api-key": api_key, "Content-Type": "application/json", "Accept": "application/json"}
    records = []
    page    = 0
    bar     = st.progress(0, text=f"Fetching {entity} from Kylas...")

    while True:
        try:
            res = requests.post(
                f"{KYLAS_BASE}{cfg['endpoint']}",
                headers=headers,
                json={"fields": cfg["fields"], "jsonRule": None},
                params={"page": page, "size": 100, "sort": "createdAt,desc"},
                timeout=20
            )
        except requests.exceptions.RequestException as e:
            st.error(f"Network error: {e}")
            break

        if res.status_code == 401:
            st.error("❌ Invalid Kylas API Key. Please check and re-enter.")
            return []
        if res.status_code == 429:
            time.sleep(60)
            continue
        if res.status_code != 200:
            st.error(f"Kylas API error {res.status_code}: {res.text[:120]}")
            break

        body        = res.json()
        content     = body.get("content", [])
        total_pages = max(body.get("totalPages", 1), 1)
        records.extend(content)

        progress = min((page + 1) / total_pages, 1.0)
        bar.progress(progress, text=f"Fetching {entity}… page {page+1}/{total_pages} ({len(records)} records)")

        if body.get("last", True) or page + 1 >= total_pages:
            break

        page += 1
        time.sleep(0.3)

    bar.empty()
    return records


# ==========================================
# DATA FLATTENER
# ==========================================
def _val(node, key="name"):
    return node.get(key) if isinstance(node, dict) else None

def _join_list(items, key="value"):
    if not items: return None
    return ", ".join(str(i.get(key,"")).strip() for i in items if i.get(key))

def _cf_label(k):
    import re
    s = re.sub(r'^cf', '', k)
    s = re.sub(r'([A-Z])', r' \1', s)
    return s.strip().title()

def flatten_records(records: list) -> pd.DataFrame:
    flat = []
    for r in records:
        d = {
            "ID":           r.get("id"),
            "Name":         r.get("name") or f"{r.get('firstName','')} {r.get('lastName','')}".strip() or None,
            "Owner":        _val(r.get("ownedBy") or r.get("assignedTo")),
            "Pipeline":     _val(r.get("pipeline")),
            "Pipeline Stage": _val(r.get("pipelineStage")),
            "Industry":     _val(r.get("industry")),
            "Employee Size":_val(r.get("numberOfEmployees")),
            "Emails":       _join_list(r.get("emails"), "value"),
            "Phones":       _join_list(r.get("phoneNumbers"), "value"),
            "Amount":       r.get("amount"),
            "Created At":   r.get("createdAt","")[:10] if r.get("createdAt") else None,
        }
        for k, v in (r.get("customFieldValues") or {}).items():
            label = _cf_label(k)
            if isinstance(v, list) and v and isinstance(v[0], dict):
                d[label] = ", ".join(i.get("name","") for i in v if i.get("name"))
            elif isinstance(v, dict):
                d[label] = v.get("name") or v.get("value")
            else:
                d[label] = v
        flat.append(d)

    df = pd.DataFrame(flat)
    df.dropna(axis=1, how="all", inplace=True)
    return df


# ==========================================
# GEMINI INTELLIGENCE
# ==========================================
def call_gemini(api_key: str, entity: str, field: str, raw_counts: dict) -> dict | None:
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            'gemini-2.5-flash',
            generation_config={"response_mime_type": "application/json"}
        )
        prompt = f"""
You are a CRM Data Visualization expert.

Entity: {entity}
Field: {field}
Raw value counts: {json.dumps(raw_counts)}

Tasks:
1. Group these raw text values into clean, standardized categories.
   Example: '10-50 employees', '10 to 50', '10-50' → all become '10–50'
2. Recommend the single best chart type: 'Bar Chart', 'Pie Chart', or 'Donut Chart'.
   - Bar = many categories or ordered data
   - Pie/Donut = 2-6 categories showing part-of-whole

Return ONLY valid JSON:
{{
  "graph_type": "Bar Chart",
  "mapping": {{
    "raw_value_1": "Standardized Category",
    "raw_value_2": "Standardized Category"
  }},
  "insight": "One sentence insight about what this data shows."
}}
"""
        res = model.generate_content(prompt)
        return json.loads(res.text)
    except Exception as e:
        st.error(f"Gemini error: {e}")
        return None


# ==========================================
# CHART RENDERER
# ==========================================
CHART_COLORS = ["#2a7aff","#06b6d4","#8b5cf6","#f59e0b","#10b981","#ef4444","#ec4899","#84cc16"]

def render_chart(viz_df: pd.DataFrame, field: str, graph_type: str):
    fig = None
    if "Bar" in graph_type:
        fig = px.bar(
            viz_df, x=field, y="Count",
            color=field,
            color_discrete_sequence=CHART_COLORS,
            template="plotly_dark",
        )
        fig.update_layout(
            paper_bgcolor="#151a22", plot_bgcolor="#151a22",
            font=dict(family="IBM Plex Mono", color="#94a3b8"),
            showlegend=False,
            xaxis=dict(gridcolor="#1e2530"),
            yaxis=dict(gridcolor="#1e2530"),
            margin=dict(l=20, r=20, t=30, b=20),
        )
    elif "Pie" in graph_type or "Donut" in graph_type:
        hole = 0.45 if "Donut" in graph_type else 0
        fig = px.pie(
            viz_df, values="Count", names=field,
            color_discrete_sequence=CHART_COLORS,
            hole=hole,
            template="plotly_dark",
        )
        fig.update_layout(
            paper_bgcolor="#151a22",
            font=dict(family="IBM Plex Mono", color="#94a3b8"),
            margin=dict(l=20, r=20, t=30, b=20),
        )
        fig.update_traces(textfont_color="#e2e8f0")

    if fig:
        st.plotly_chart(fig, use_container_width=True)


# ==========================================
# SESSION STATE INIT
# ==========================================
for key, default in [
    ("kylas_key", ""), ("gemini_key", ""),
    ("keys_set", False), ("records", []),
    ("df", None), ("entity", None),
    ("analysis", None), ("analyzed_field", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.markdown("### ⚡ KYLAS INTELLIGENCE")
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── API Keys ──────────────────────────────
    st.markdown("**API CONFIGURATION**")
    kylas_input  = st.text_input("Kylas API Key",  type="password", value=st.session_state.kylas_key,  placeholder="xxxx:xxxxx")
    gemini_input = st.text_input("Gemini API Key", type="password", value=st.session_state.gemini_key, placeholder="AIza...")

    if st.button("Save Keys"):
        if kylas_input and gemini_input:
            st.session_state.kylas_key  = kylas_input
            st.session_state.gemini_key = gemini_input
            st.session_state.keys_set   = True
            st.success("✅ Keys saved")
        else:
            st.error("Both keys required")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── Entity & Fetch ─────────────────────────
    if st.session_state.keys_set:
        st.markdown("**DATA SOURCE**")
        entity = st.selectbox("Module", list(ENTITY_CONFIG.keys()))

        if st.button("Fetch Data from Kylas"):
            with st.spinner(f"Loading {entity}..."):
                records = kylas_fetch_all(st.session_state.kylas_key, entity)
            if records:
                st.session_state.records = records
                st.session_state.df      = flatten_records(records)
                st.session_state.entity  = entity
                st.session_state.analysis = None
                st.success(f"✅ {len(records)} {entity} loaded")
            else:
                st.warning("No records returned.")

        # ── Field selection ────────────────────
        if st.session_state.df is not None and st.session_state.entity == entity:
            df = st.session_state.df
            exclude = {"ID", "Name", "Emails", "Phones", "Created At", "Amount"}
            analyzable = [c for c in df.columns if c not in exclude and df[c].nunique() <= 50 and df[c].nunique() >= 2]

            if analyzable:
                st.markdown('<hr class="divider">', unsafe_allow_html=True)
                st.markdown("**ANALYSIS**")
                field = st.selectbox("Field to Analyze", analyzable)

                if st.button("Run Gemini Analysis"):
                    raw_counts = df[field].value_counts().to_dict()
                    raw_counts = {str(k): int(v) for k, v in raw_counts.items()}

                    with st.spinner("🧠 Gemini analyzing..."):
                        result = call_gemini(st.session_state.gemini_key, entity, field, raw_counts)

                    if result:
                        st.session_state.analysis       = result
                        st.session_state.analyzed_field = field

                        # Save to version history
                        entry = {
                            "id":         datetime.now().strftime("%Y%m%d_%H%M%S"),
                            "timestamp":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "entity":     entity,
                            "field":      field,
                            "graph_type": result.get("graph_type"),
                            "insight":    result.get("insight", ""),
                            "mapping":    result.get("mapping", {}),
                            "raw_counts": raw_counts,
                        }
                        save_to_history(entry)
                        st.success("✅ Analysis complete + saved to history")
    else:
        st.info("Enter API keys above to begin.")


# ==========================================
# MAIN AREA
# ==========================================
tab1, tab2, tab3 = st.tabs(["📊  ANALYSIS", "🗃  DATA TABLE", "🕘  VERSION HISTORY"])

# ── Tab 1: Analysis ────────────────────────────────────────
with tab1:
    if st.session_state.analysis and st.session_state.df is not None:
        intel  = st.session_state.analysis
        field  = st.session_state.analyzed_field
        df     = st.session_state.df
        entity = st.session_state.entity

        # Apply mapping
        mapping  = intel.get("mapping", {})
        df["_std"] = df[field].astype(str).map(mapping).fillna("Other")
        viz_df   = df["_std"].value_counts().reset_index()
        viz_df.columns = [field, "Count"]

        # Header
        st.markdown(f"""
        <div class="intel-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <span style="font-family:'IBM Plex Mono';font-size:18px;font-weight:600;">{entity} → {field}</span><br>
                    <span style="color:#64748b;font-size:12px;">{datetime.now().strftime('%Y-%m-%d %H:%M')}</span>
                </div>
                <span class="tag tag-blue">{intel.get('graph_type','')}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Metrics row
        total   = int(df[field].notna().sum())
        cats    = viz_df.shape[0]
        top_cat = viz_df.iloc[0][field] if not viz_df.empty else "—"
        top_pct = f"{viz_df.iloc[0]['Count']/total*100:.0f}%" if not viz_df.empty else "—"

        st.markdown(f"""
        <div class="metric-row">
            <div class="metric-box"><div class="val">{total:,}</div><div class="lbl">Records</div></div>
            <div class="metric-box"><div class="val">{cats}</div><div class="lbl">Categories</div></div>
            <div class="metric-box"><div class="val">{top_pct}</div><div class="lbl">Top: {top_cat}</div></div>
        </div>
        """, unsafe_allow_html=True)

        # Chart
        render_chart(viz_df, field, intel.get("graph_type","Bar Chart"))

        # Insight
        if intel.get("insight"):
            st.markdown(f"""
            <div class="intel-card" style="border-left: 3px solid #2a7aff;">
                <span style="color:#64748b;font-size:11px;font-family:'IBM Plex Mono';text-transform:uppercase;letter-spacing:1px;">AI INSIGHT</span><br>
                <span style="font-size:14px;">{intel['insight']}</span>
            </div>
            """, unsafe_allow_html=True)

        # Mapping expander
        with st.expander("View Category Mapping (Gemini Output)"):
            st.json(intel)

    else:
        st.markdown("""
        <div style="text-align:center;padding:80px 0;color:#334155;">
            <div style="font-size:48px;margin-bottom:16px;">⚡</div>
            <div style="font-family:'IBM Plex Mono';font-size:16px;">Enter API keys → Fetch data → Run analysis</div>
        </div>
        """, unsafe_allow_html=True)


# ── Tab 2: Data Table ──────────────────────────────────────
with tab2:
    if st.session_state.df is not None:
        df = st.session_state.df
        st.markdown(f"**{st.session_state.entity}** — {len(df):,} records, {len(df.columns)} columns")
        st.dataframe(df, use_container_width=True, height=500)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇ Download CSV", csv, f"{st.session_state.entity}_kylas.csv", "text/csv")
    else:
        st.info("Fetch data first from the sidebar.")


# ── Tab 3: Version History ─────────────────────────────────
with tab3:
    history = load_history()

    if not history:
        st.info("No analysis runs yet. Run an analysis to see history here.")
    else:
        st.markdown(f"**{len(history)} analysis runs saved**")

        # Filter controls
        col1, col2 = st.columns([1, 1])
        with col1:
            filter_entity = st.selectbox("Filter by Entity", ["All"] + list(ENTITY_CONFIG.keys()))
        with col2:
            if st.button("🗑 Clear All History"):
                if os.path.exists(HISTORY_FILE):
                    os.remove(HISTORY_FILE)
                st.rerun()

        for entry in history:
            if filter_entity != "All" and entry.get("entity") != filter_entity:
                continue

            with st.expander(f"[{entry['timestamp']}]  {entry['entity']} → {entry['field']}  |  {entry['graph_type']}"):

                # Replay chart from history
                mapping    = entry.get("mapping", {})
                raw_counts = entry.get("raw_counts", {})

                if raw_counts and mapping:
                    # Rebuild viz_df from raw_counts + mapping
                    rows = []
                    for raw_val, count in raw_counts.items():
                        std_val = mapping.get(raw_val, "Other")
                        rows.append({"_cat": std_val, "Count": count})

                    if rows:
                        hist_df = pd.DataFrame(rows).groupby("_cat", as_index=False)["Count"].sum()
                        hist_df.columns = [entry["field"], "Count"]

                        # Metrics
                        total_h = hist_df["Count"].sum()
                        st.markdown(f"""
                        <div class="metric-row">
                            <div class="metric-box"><div class="val">{total_h:,}</div><div class="lbl">Records</div></div>
                            <div class="metric-box"><div class="val">{len(hist_df)}</div><div class="lbl">Categories</div></div>
                        </div>
                        """, unsafe_allow_html=True)

                        render_chart(hist_df, entry["field"], entry["graph_type"])

                if entry.get("insight"):
                    st.markdown(f"> 💡 {entry['insight']}")

                col_a, col_b = st.columns(2)
                with col_a:
                    st.json({"mapping": mapping})
                with col_b:
                    st.json({"raw_counts": raw_counts})
