import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px
import json
import os
import re
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

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

/* ── Base ── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background-color: #f8fafc;
    color: #1e293b;
}
.stApp { background-color: #f8fafc; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background-color: #ffffff !important;
    border-right: 1px solid #e2e8f0 !important;
}
[data-testid="stSidebar"] * { color: #1e293b !important; }
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] label { color: #64748b !important; font-size: 12px !important; }
[data-testid="stSidebar"] strong { color: #0f172a !important; font-size: 11px !important;
    letter-spacing: 0.08em; text-transform: uppercase; }

/* ── Cards ── */
.intel-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.intel-card:hover { border-color: #3b82f6; box-shadow: 0 4px 12px rgba(59,130,246,0.08); transition: all 0.2s; }

/* ── Metrics ── */
.metric-row { display: flex; gap: 12px; margin-bottom: 20px; }
.metric-box {
    flex: 1;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 18px 16px;
    text-align: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.metric-box .val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 26px;
    font-weight: 700;
    color: #2563eb;
    line-height: 1.2;
}
.metric-box .lbl {
    font-size: 11px;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 4px;
}

/* ── Level headers ── */
.slice-header {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-left: 4px solid #3b82f6;
    border-radius: 8px;
    padding: 12px 18px;
    margin: 20px 0 12px 0;
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    color: #1e40af;
}
.slice-l2 {
    background: #f5f3ff !important;
    border-color: #ddd6fe !important;
    border-left-color: #7c3aed !important;
    color: #5b21b6 !important;
}
.slice-l3 {
    background: #fffbeb !important;
    border-color: #fde68a !important;
    border-left-color: #d97706 !important;
    color: #92400e !important;
}

/* ── Tags ── */
.tag {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    letter-spacing: 0.03em;
}
.tag-blue   { background: #dbeafe; color: #1d4ed8; }
.tag-purple { background: #ede9fe; color: #6d28d9; }
.tag-amber  { background: #fef3c7; color: #b45309; }

/* ── Buttons ── */
.stButton > button {
    background: #2563eb !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    padding: 9px 20px !important;
    width: 100%;
    box-shadow: 0 1px 3px rgba(37,99,235,0.3) !important;
    transition: all 0.15s !important;
}
.stButton > button:hover {
    background: #1d4ed8 !important;
    box-shadow: 0 4px 12px rgba(37,99,235,0.35) !important;
    transform: translateY(-1px) !important;
}

/* ── Inputs ── */
.stTextInput input {
    background: #f8fafc !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 8px !important;
    color: #1e293b !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 13px !important;
    padding: 8px 12px !important;
}
.stTextInput input:focus {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.1) !important;
}

/* ── Selectbox ── */
.stSelectbox > div > div {
    background: #f8fafc !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 8px !important;
    color: #1e293b !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: #f1f5f9;
    border-radius: 10px;
    padding: 4px;
    gap: 2px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 7px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    color: #64748b !important;
    padding: 8px 16px !important;
}
.stTabs [aria-selected="true"] {
    background: #ffffff !important;
    color: #1e293b !important;
    font-weight: 600 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08) !important;
}

/* ── Expanders ── */
.streamlit-expanderHeader {
    background: #f8fafc !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 8px !important;
    font-size: 13px !important;
    color: #475569 !important;
    font-weight: 500 !important;
}

/* ── Divider ── */
.divider { border: none; border-top: 1px solid #e2e8f0; margin: 20px 0; }

/* ── Headings ── */
h1 { color: #0f172a !important; font-size: 20px !important; font-weight: 700 !important; }
h2, h3 { color: #1e293b !important; }

/* ── Dataframe ── */
.stDataFrame { border: 1px solid #e2e8f0 !important; border-radius: 8px !important; overflow: hidden; }

/* ── Success / Error / Info ── */
.stSuccess { background: #f0fdf4 !important; border-color: #86efac !important; color: #166534 !important; border-radius: 8px !important; }
.stError   { background: #fef2f2 !important; border-color: #fca5a5 !important; color: #991b1b !important; border-radius: 8px !important; }
.stInfo    { background: #eff6ff !important; border-color: #93c5fd !important; color: #1e40af !important; border-radius: 8px !important; }

/* ── Hide branding ── */
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# CONSTANTS
# ==========================================
HISTORY_FILE = "crm_intelligence_history.json"
ENTITY_LIST  = ["Leads", "Contacts", "Companies", "Deals"]
EXCLUDE_COLS = {"ID", "Name", "Emails", "Phones", "Created At", "Amount", "Updated At"}
CHART_COLORS = ["#3b82f6","#8b5cf6","#f59e0b","#10b981","#ef4444","#ec4899","#06b6d4","#84cc16"]
LEVEL_COLORS = ["#2563eb", "#7c3aed", "#d97706"]

# ==========================================
# HISTORY — API KEYS NEVER STORED
# ==========================================
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_to_history(entry: dict):
    BANNED = {"kylas_key", "gemini_key", "api_key", "key", "token", "secret"}
    safe   = {k: v for k, v in entry.items() if k.lower() not in BANNED}
    hist   = load_history()
    hist.insert(0, safe)
    with open(HISTORY_FILE, "w") as f:
        json.dump(hist[:100], f, indent=2)

# ==========================================
# CSV LOADER
# ==========================================
def load_csv(uploaded_file) -> pd.DataFrame:
    df = pd.read_csv(uploaded_file, dtype=str).fillna("")
    # Strip whitespace from all string cells
    df = df.apply(lambda col: col.str.strip() if col.dtype == object else col)

    # FIX: Deduplicate column names — Kylas exports often have repeated headers
    # e.g. two columns both "Owner" → renamed to "Owner", "Owner_2"
    seen = {}
    new_cols = []
    for col in df.columns:
        col_clean = str(col).strip()
        if col_clean in seen:
            seen[col_clean] += 1
            new_cols.append(f"{col_clean}_{seen[col_clean]}")
        else:
            seen[col_clean] = 1
            new_cols.append(col_clean)
    df.columns = new_cols

    # Auto-rename common Kylas export column names to standard names
    rename_map = {}
    for col in df.columns:
        low = col.lower().strip()
        # Remove trailing _2, _3 etc added by dedup before matching
        base_low = re.sub(r"_\d+$", "", low)
        if base_low in ("id","lead id","contact id","company id","deal id"):
            rename_map[col] = col  # keep as-is, ID already fine
        elif base_low in ("name","full name","company name","lead name","contact name"):
            rename_map[col] = "Name" if col == base_low or "name" in base_low else col
        elif any(x in base_low for x in ("number of employee","no of employee","no. of employee",
                                          "employee size","employee count","numberofemployee")):
            rename_map[col] = "Employee Size"
        elif base_low in ("industry","sector"):
            rename_map[col] = "Industry"
        elif "pipeline stage" in base_low:
            rename_map[col] = "Pipeline Stage"
        elif base_low == "owner" or base_low == "owned by":
            rename_map[col] = "Owner"

    if rename_map:
        df.rename(columns=rename_map, inplace=True)

    # Final dedup pass after rename (renaming may create new duplicates)
    seen2 = {}
    final_cols = []
    for col in df.columns:
        if col in seen2:
            seen2[col] += 1
            final_cols.append(f"{col}_{seen2[col]}")
        else:
            seen2[col] = 1
            final_cols.append(col)
    df.columns = pd.Index(final_cols)

    return df

def get_analyzable_cols(df: pd.DataFrame) -> list:
    """Safely find categorical columns — coerces to str first to avoid
    ValueError on mixed-type / list-cell columns in large Kylas exports."""
    result = []
    for c in df.columns:
        if c in EXCLUDE_COLS:
            continue
        try:
            n = df[c].astype(str).nunique()
            if 2 <= n <= 50:
                result.append(c)
        except Exception:
            continue
    return result

# ==========================================
# GEMINI
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
Entity: {entity} | Field: {field}
Raw value counts: {json.dumps(raw_counts)}

1. Group raw text values into clean standardized categories.
2. Recommend best chart: 'Bar Chart', 'Pie Chart', or 'Donut Chart'.
   Bar = many categories or ordered data. Pie/Donut = 2-6 part-of-whole categories.

Return ONLY valid JSON:
{{
  "graph_type": "Bar Chart",
  "mapping": {{"raw_val": "Standardized Category"}},
  "insight": "One sentence insight about this data."
}}"""
        res = model.generate_content(prompt)
        return json.loads(res.text)
    except Exception as e:
        st.error(f"Gemini error: {e}")
        return None

# ==========================================
# CHART RENDERER
# ==========================================
def render_chart(viz_df: pd.DataFrame, field: str, graph_type: str, height: int = 300):
    if viz_df.empty:
        st.info("No data to display.")
        return
    layout = dict(
        paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
        font=dict(family="Inter", color="#475569", size=12),
        margin=dict(l=20, r=20, t=30, b=20),
        height=height,
    )
    if "Bar" in graph_type:
        fig = px.bar(viz_df, x=field, y="Count", color=field,
                     color_discrete_sequence=CHART_COLORS, template="plotly_white")
        fig.update_layout(**layout, showlegend=False,
                          xaxis=dict(gridcolor="#f1f5f9", linecolor="#e2e8f0", tickfont=dict(color="#64748b")),
                          yaxis=dict(gridcolor="#f1f5f9", linecolor="#e2e8f0", tickfont=dict(color="#64748b")))
    else:
        hole = 0.45 if "Donut" in graph_type else 0
        fig  = px.pie(viz_df, values="Count", names=field,
                      color_discrete_sequence=CHART_COLORS, hole=hole, template="plotly_white")
        fig.update_layout(**layout)
        fig.update_traces(textfont_color="#1e293b", textfont_size=12)
    st.plotly_chart(fig, use_container_width=True)

# ==========================================
# DRILL-DOWN SLICER — recursive, max 3 levels
# ==========================================
def apply_mapping(df: pd.DataFrame, field: str, mapping: dict):
    df  = df.copy()
    col = f"_std_{field}"
    df[col] = df[field].astype(str).replace("nan", "").map(mapping).fillna("Other")
    return df, col

def render_slicer(df: pd.DataFrame, entity: str, gemini_key: str,
                  level: int = 1, parent_label: str = ""):
    if df is None or len(df) == 0:
        st.info("No records in this slice.")
        return

    analyzable = get_analyzable_cols(df)
    if not analyzable:
        st.info("No categorical columns available to slice further.")
        return

    color     = LEVEL_COLORS[level - 1]
    css_extra = f"slice-l{level}" if level > 1 else ""
    crumb     = f"  →  {parent_label}" if parent_label else ""
    uid       = f"l{level}_{abs(hash(parent_label)) % 100000}"

    st.markdown(f"""
    <div class="slice-header {css_extra}">
        <span style="color:{color};font-weight:600;">▶ LEVEL {level}</span>&nbsp;&nbsp;
        <span style="color:#94a3b8;">{entity}{crumb}</span>&nbsp;&nbsp;
        <span style="color:#475569;font-size:11px;">{len(df):,} records</span>
    </div>
    """, unsafe_allow_html=True)

    col_sel, col_btn = st.columns([4, 1])
    with col_sel:
        field = st.selectbox(f"Analyze field (Level {level})", analyzable, key=f"field_{uid}")
    with col_btn:
        st.markdown("<div style='margin-top:26px'>", unsafe_allow_html=True)
        run = st.button("Analyze ▶", key=f"run_{uid}")
        st.markdown("</div>", unsafe_allow_html=True)

    result_key = f"result_{uid}"

    if run:
        raw_counts = {str(k): int(v) for k, v in df[field].astype(str).value_counts().items()}
        with st.spinner(f"🧠 Gemini analyzing {field}..."):
            result = call_gemini(gemini_key, entity, field, raw_counts)
        if result:
            st.session_state[result_key] = {"field": field, "result": result, "raw_counts": raw_counts}
            save_to_history({
                "id":         datetime.now().strftime("%Y%m%d_%H%M%S"),
                "timestamp":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "entity":     entity,
                "field":      field,
                "level":      level,
                "parent":     parent_label,
                "graph_type": result.get("graph_type"),
                "insight":    result.get("insight", ""),
                "mapping":    result.get("mapping", {}),
                "raw_counts": raw_counts,
            })

    if result_key not in st.session_state:
        return

    saved   = st.session_state[result_key]
    field   = saved["field"]
    result  = saved["result"]
    mapping = result.get("mapping", {})

    df_mapped, std_col = apply_mapping(df, field, mapping)
    viz_df = df_mapped[std_col].value_counts().reset_index()
    viz_df.columns = [field, "Count"]

    total   = int(viz_df["Count"].sum())
    top_cat = viz_df.iloc[0][field] if not viz_df.empty else "—"
    top_pct = f"{viz_df.iloc[0]['Count']/total*100:.0f}%" if total > 0 else "—"

    st.markdown(f"""
    <div class="metric-row">
        <div class="metric-box"><div class="val">{total:,}</div><div class="lbl">Records</div></div>
        <div class="metric-box"><div class="val">{viz_df.shape[0]}</div><div class="lbl">Categories</div></div>
        <div class="metric-box">
            <div class="val" style="font-size:20px;color:{color};">{top_pct}</div>
            <div class="lbl">Top: {top_cat}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    render_chart(viz_df, field, result.get("graph_type", "Bar Chart"), height=280)

    if result.get("insight"):
        st.markdown(f"""
        <div class="intel-card" style="border-left:3px solid {color};padding:12px 16px;margin:8px 0 16px 0;">
            <span style="color:#64748b;font-size:10px;font-family:'IBM Plex Mono';">AI INSIGHT</span><br>
            <span style="font-size:13px;">{result['insight']}</span>
        </div>
        """, unsafe_allow_html=True)

    # ── Drill Down (max level 3) ──────────────────────────
    if level < 3:
        categories = sorted(viz_df[field].tolist())
        st.markdown("""
        <div style="font-family:'IBM Plex Mono';font-size:11px;color:#475569;
                    letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;">
            Drill into a category ↓
        </div>
        """, unsafe_allow_html=True)

        col_d1, col_d2 = st.columns([4, 1])
        with col_d1:
            selected_cat = st.selectbox(
                f"Filter by {field}",
                ["— view all —"] + categories,
                key=f"drill_cat_{uid}"
            )
        with col_d2:
            st.markdown("<div style='margin-top:26px'>", unsafe_allow_html=True)
            drill_clicked = st.button("Drill ↓", key=f"drill_btn_{uid}")
            st.markdown("</div>", unsafe_allow_html=True)

        drill_state = f"drilled_{uid}"

        if drill_clicked:
            if selected_cat == "— view all —":
                st.session_state[drill_state] = (df_mapped.drop(columns=[std_col]), "All")
            else:
                sub = df_mapped[df_mapped[std_col] == selected_cat].drop(columns=[std_col])
                st.session_state[drill_state] = (sub, selected_cat)

        if drill_state in st.session_state:
            drilled_df, drill_label = st.session_state[drill_state]
            new_parent = f"{parent_label} → {field}: {drill_label}" if parent_label else f"{field}: {drill_label}"
            next_color = LEVEL_COLORS[level]

            st.markdown(f"<div style='margin-top:8px;padding-left:16px;border-left:2px solid {next_color}33;'>",
                        unsafe_allow_html=True)
            render_slicer(drilled_df, entity, gemini_key, level=level + 1, parent_label=new_parent)
            st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# SESSION STATE INIT
# ==========================================
for key, default in [
    ("gemini_key", ""), ("gemini_set", False),
    ("df", None), ("entity", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.markdown("""
    <div style="padding:4px 0 12px 0;">
        <div style="font-size:18px;font-weight:700;color:#0f172a;letter-spacing:-0.3px;">⚡ Kylas Intelligence</div>
        <div style="font-size:11px;color:#94a3b8;margin-top:2px;">CRM Drill-Down Analyzer</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── Gemini Key only ───────────────────
    st.markdown("**GEMINI API KEY**")
    gemini_input = st.text_input("", type="password",
                                  value=st.session_state.gemini_key,
                                  placeholder="AIza...",
                                  label_visibility="collapsed")
    if st.button("Save Key"):
        if gemini_input:
            st.session_state.gemini_key = gemini_input
            st.session_state.gemini_set = True
            st.success("✅ Saved to session only")
        else:
            st.error("Enter your Gemini API key")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── CSV Upload ────────────────────────
    st.markdown("**DATA SOURCE**")
    entity   = st.selectbox("Module", ENTITY_LIST)
    uploaded = st.file_uploader(f"Upload {entity} CSV", type=["csv"],
                                 help="Export from Kylas → Reports → Export CSV")

    if uploaded:
        try:
            df_up = load_csv(uploaded)
            st.session_state.df     = df_up
            st.session_state.entity = entity
            st.success(f"✅ {len(df_up):,} rows · {len(df_up.columns)} cols")
            with st.expander(f"📋 {len(df_up.columns)} columns detected"):
                analyzable = get_analyzable_cols(df_up)
                st.markdown(f"""
                <div style="font-family:'IBM Plex Mono';font-size:10px;margin-bottom:8px;">
                    <span style="color:#4ade80;">🔬 {len(analyzable)} analyzable</span>&nbsp;·&nbsp;
                    <span style="color:#475569;">{len(df_up.columns)-len(analyzable)} skipped</span>
                </div>""", unsafe_allow_html=True)
                for c in df_up.columns:
                    nuniq = df_up[c].astype(str).nunique()
                    is_dup = re.search(r"_\d+$", c)
                    is_analyzable = c in analyzable
                    icon  = "🔬" if is_analyzable else ("⚠️" if is_dup else "·")
                    color = "#4ade80" if is_analyzable else ("#f59e0b" if is_dup else "#475569")
                    label = f"{c} <span style='color:#334155;'>(duplicate)</span>" if is_dup else c
                    st.markdown(
                        f"<div style='font-family:IBM Plex Mono;font-size:11px;padding:2px 0;"
                        f"color:{color};'>{icon} {label} "
                        f"<span style='color:#334155;'>· {nuniq} unique</span></div>",
                        unsafe_allow_html=True
                    )
        except Exception as e:
            st.error(f"CSV read error: {e}")

    with st.expander("📤 How to export from Kylas?"):
        st.markdown("""
        <div style="font-family:'IBM Plex Mono';font-size:11px;color:#64748b;line-height:2;">
        <span style="color:#2a7aff;">1.</span> Open Kylas CRM<br>
        <span style="color:#2a7aff;">2.</span> Go to <b style="color:#94a3b8;">Leads / Contacts / Companies / Deals</b><br>
        <span style="color:#2a7aff;">3.</span> Top right → <b style="color:#94a3b8;">⋮ More</b> → <b style="color:#94a3b8;">Export</b><br>
        <span style="color:#2a7aff;">4.</span> Select <b style="color:#94a3b8;">All fields</b> → Download CSV<br>
        <span style="color:#2a7aff;">5.</span> Upload the file above
        </div>
        """, unsafe_allow_html=True)

# ==========================================
# MAIN AREA
# ==========================================
tab1, tab2, tab3 = st.tabs(["🔬  DRILL-DOWN SLICER", "🗃  DATA TABLE", "🕘  VERSION HISTORY"])

# ── Tab 1: Drill-Down Slicer ──────────────────────────────
with tab1:
    if st.session_state.df is not None and st.session_state.gemini_key:
        ent = st.session_state.entity or entity
        st.markdown(f"""
        <div class="intel-card" style="margin-bottom:24px;">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
                <span style="font-family:'IBM Plex Mono';font-size:16px;font-weight:600;">
                    {ent} — Drill-Down Analysis
                </span>
                <div>
                    <span class="tag tag-blue">L1 Field</span>&nbsp;
                    <span class="tag tag-purple">L2 Drill</span>&nbsp;
                    <span class="tag tag-amber">L3 Drill</span>
                </div>
            </div>
            <div style="color:#64748b;font-size:12px;margin-top:8px;">
                Pick a field → Analyze with Gemini → Drill into any category → Analyze again (max 3 levels)
            </div>
        </div>
        """, unsafe_allow_html=True)

        render_slicer(
            st.session_state.df,
            ent,
            st.session_state.gemini_key,
            level=1,
            parent_label=""
        )

    else:
        # Pre-compute all conditional values BEFORE building HTML
        gemini_done = bool(st.session_state.gemini_key)
        data_done   = st.session_state.df is not None
        both_done   = gemini_done and data_done

        # Step 1 values
        s1_bg    = "#dcfce7" if gemini_done else "#dbeafe"
        s1_color = "#166534" if gemini_done else "#1d4ed8"
        s1_icon  = "✓"      if gemini_done else "1"
        s1_title = "Gemini API key saved"    if gemini_done else "Enter your Gemini API key"
        s1_sub   = "Ready to analyze"        if gemini_done else "Sidebar → Gemini API Key → Save Key"

        # Step 2 values
        s2_bg    = "#dcfce7" if data_done else "#dbeafe"
        s2_color = "#166534" if data_done else "#1d4ed8"
        s2_icon  = "✓"      if data_done else "2"
        s2_title = "CSV loaded"              if data_done else "Upload your Kylas CSV"
        s2_sub   = "Data ready"              if data_done else "Sidebar → Upload CSV → Browse files"

        # Step 3 values
        s3_opacity = "1" if both_done else "0.35"

        st.markdown(f"""
        <div style="max-width:460px;margin:60px auto 0 auto;">
            <div style="font-size:11px;font-weight:700;color:#94a3b8;
                        letter-spacing:0.1em;text-transform:uppercase;margin-bottom:28px;">
                Get Started
            </div>

            <div style="display:flex;align-items:flex-start;gap:16px;margin-bottom:24px;">
                <div style="min-width:32px;height:32px;border-radius:50%;display:flex;align-items:center;
                    justify-content:center;font-size:13px;font-weight:700;
                    background:{s1_bg};color:{s1_color};">{s1_icon}</div>
                <div style="padding-top:4px;">
                    <div style="font-size:14px;font-weight:600;color:#1e293b;">{s1_title}</div>
                    <div style="font-size:12px;color:#94a3b8;margin-top:3px;">{s1_sub}</div>
                </div>
            </div>

            <div style="display:flex;align-items:flex-start;gap:16px;margin-bottom:24px;">
                <div style="min-width:32px;height:32px;border-radius:50%;display:flex;align-items:center;
                    justify-content:center;font-size:13px;font-weight:700;
                    background:{s2_bg};color:{s2_color};">{s2_icon}</div>
                <div style="padding-top:4px;">
                    <div style="font-size:14px;font-weight:600;color:#1e293b;">{s2_title}</div>
                    <div style="font-size:12px;color:#94a3b8;margin-top:3px;">{s2_sub}</div>
                </div>
            </div>

            <div style="display:flex;align-items:flex-start;gap:16px;opacity:{s3_opacity};">
                <div style="min-width:32px;height:32px;border-radius:50%;display:flex;align-items:center;
                    justify-content:center;font-size:13px;font-weight:700;
                    background:#dbeafe;color:#1d4ed8;">3</div>
                <div style="padding-top:4px;">
                    <div style="font-size:14px;font-weight:600;color:#1e293b;">Pick a field and click Analyze</div>
                    <div style="font-size:12px;color:#94a3b8;margin-top:3px;">Gemini will suggest chart type and group categories</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ── Tab 2: Data Table ─────────────────────────────────────
with tab2:
    if st.session_state.df is not None:
        df  = st.session_state.df
        ent = st.session_state.entity or "Data"
        st.markdown(f"**{ent}** — {len(df):,} records · {len(df.columns)} columns")

        show_cols = st.multiselect(
            "Columns to show",
            df.columns.tolist(),
            default=df.columns.tolist()[:12]
        )
        if show_cols:
            st.dataframe(df[show_cols], use_container_width=True, height=500)

        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇ Download CSV", csv_bytes, f"{ent}_export.csv", "text/csv")
    else:
        st.info("Upload a CSV from the sidebar first.")

# ── Tab 3: Version History ────────────────────────────────
with tab3:
    history = load_history()

    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.markdown(
            f"**{len(history)} runs saved** &nbsp;·&nbsp;"
            f"<span style='color:#4ade80;font-size:12px;'>🔒 API keys never stored</span>",
            unsafe_allow_html=True
        )
    with col_h2:
        if st.button("🗑 Clear All"):
            if os.path.exists(HISTORY_FILE):
                os.remove(HISTORY_FILE)
            st.rerun()

    if not history:
        st.info("No analysis runs yet.")
    else:
        filter_entity = st.selectbox("Filter by Entity", ["All"] + ENTITY_LIST)

        for entry in history:
            if filter_entity != "All" and entry.get("entity") != filter_entity:
                continue

            level      = entry.get("level", 1)
            parent     = entry.get("parent", "")
            color      = LEVEL_COLORS[min(level - 1, 2)]
            breadcrumb = f" → {parent}" if parent else ""
            label      = (f"[{entry.get('timestamp','')}]  "
                          f"{entry.get('entity','')} {breadcrumb} → {entry.get('field','')}  "
                          f"| L{level} | {entry.get('graph_type','')}")

            with st.expander(label):
                mapping    = entry.get("mapping", {})
                raw_counts = entry.get("raw_counts", {})

                if raw_counts and mapping:
                    rows = [{"_cat": mapping.get(rv, "Other"), "Count": cnt}
                            for rv, cnt in raw_counts.items()]
                    if rows:
                        hist_df = pd.DataFrame(rows).groupby("_cat", as_index=False)["Count"].sum()
                        hist_df.columns = [entry["field"], "Count"]
                        total_h = hist_df["Count"].sum()

                        st.markdown(f"""
                        <div style="display:flex;gap:12px;margin-bottom:12px;">
                            <div style="flex:1;background:#151a22;border:1px solid #1e2b3c;border-radius:6px;padding:12px;text-align:center;">
                                <div style="font-family:'IBM Plex Mono';font-size:22px;font-weight:600;color:{color};">{total_h:,}</div>
                                <div style="font-size:10px;color:#64748b;">RECORDS</div>
                            </div>
                            <div style="flex:1;background:#151a22;border:1px solid #1e2b3c;border-radius:6px;padding:12px;text-align:center;">
                                <div style="font-family:'IBM Plex Mono';font-size:22px;font-weight:600;color:{color};">{len(hist_df)}</div>
                                <div style="font-size:10px;color:#64748b;">CATEGORIES</div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        render_chart(hist_df, entry["field"], entry.get("graph_type","Bar Chart"), height=220)

                if entry.get("insight"):
                    st.markdown(f"> 💡 {entry['insight']}")

                col_a, col_b = st.columns(2)
                with col_a:
                    st.json({"mapping": mapping})
                with col_b:
                    st.json({"raw_counts": raw_counts})
