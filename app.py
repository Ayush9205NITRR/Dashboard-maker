# v6 — light theme, fixed get-started, no broken HTML
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

html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #f8fafc; color: #1e293b; }
.stApp { background-color: #f8fafc; }

[data-testid="stSidebar"] { background-color: #ffffff !important; border-right: 1px solid #e2e8f0 !important; }
[data-testid="stSidebar"] * { color: #1e293b !important; }

.intel-card { background:#ffffff; border:1px solid #e2e8f0; border-radius:12px; padding:20px 24px; margin-bottom:16px; box-shadow:0 1px 3px rgba(0,0,0,0.04); }
.intel-card:hover { border-color:#3b82f6; transition:border-color 0.2s; }

.metric-row { display:flex; gap:12px; margin-bottom:20px; }
.metric-box { flex:1; background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:18px 16px; text-align:center; box-shadow:0 1px 3px rgba(0,0,0,0.04); }
.metric-box .val { font-family:'JetBrains Mono',monospace; font-size:26px; font-weight:700; color:#2563eb; line-height:1.2; }
.metric-box .lbl { font-size:11px; color:#94a3b8; text-transform:uppercase; letter-spacing:0.08em; margin-top:4px; }

.slice-header { background:#eff6ff; border:1px solid #bfdbfe; border-left:4px solid #3b82f6; border-radius:8px; padding:12px 18px; margin:20px 0 12px 0; font-size:13px; color:#1e40af; }
.slice-l2 { background:#f5f3ff !important; border-color:#ddd6fe !important; border-left-color:#7c3aed !important; color:#5b21b6 !important; }
.slice-l3 { background:#fffbeb !important; border-color:#fde68a !important; border-left-color:#d97706 !important; color:#92400e !important; }

.tag { display:inline-block; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:600; }
.tag-blue   { background:#dbeafe; color:#1d4ed8; }
.tag-purple { background:#ede9fe; color:#6d28d9; }
.tag-amber  { background:#fef3c7; color:#b45309; }

.stButton > button { background:#2563eb !important; color:white !important; border:none !important; border-radius:8px !important; font-size:13px !important; font-weight:600 !important; padding:9px 20px !important; width:100%; }
.stButton > button:hover { background:#1d4ed8 !important; }

.stTextInput input { background:#f8fafc !important; border:1px solid #cbd5e1 !important; border-radius:8px !important; color:#1e293b !important; font-size:13px !important; }

.stTabs [data-baseweb="tab-list"] { background:#f1f5f9; border-radius:10px; padding:4px; gap:2px; }
.stTabs [data-baseweb="tab"] { border-radius:7px !important; font-size:13px !important; font-weight:500 !important; color:#64748b !important; padding:8px 16px !important; }
.stTabs [aria-selected="true"] { background:#ffffff !important; color:#1e293b !important; font-weight:600 !important; box-shadow:0 1px 3px rgba(0,0,0,0.08) !important; }

.divider { border:none; border-top:1px solid #e2e8f0; margin:20px 0; }
h1 { color:#0f172a !important; font-size:20px !important; font-weight:700 !important; }
h2, h3 { color:#1e293b !important; }
.stDataFrame { border:1px solid #e2e8f0 !important; border-radius:8px !important; overflow:hidden; }
#MainMenu, footer, header { visibility:hidden; }
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
# HISTORY
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
    df = df.apply(lambda col: col.str.strip() if col.dtype == object else col)

    # Deduplicate column names
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

    # Auto-rename common Kylas column names
    rename_map = {}
    for col in df.columns:
        low      = col.lower().strip()
        base_low = re.sub(r"_\d+$", "", low)
        if any(x in base_low for x in ("number of employee", "no of employee", "no. of employee",
                                        "employee size", "employee count", "numberofemployee", "employees")):
            rename_map[col] = "Employee Size"
        elif base_low in ("industry", "sector"):
            rename_map[col] = "Industry"
        elif "pipeline stage" in base_low:
            rename_map[col] = "Pipeline Stage"
        elif base_low in ("owner", "owned by"):
            rename_map[col] = "Owner"
        elif base_low in ("name", "full name", "company name", "lead name", "contact name"):
            rename_map[col] = "Name"

    if rename_map:
        df.rename(columns=rename_map, inplace=True)

    # Final dedup pass after rename
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
def call_gemini(api_key: str, entity: str, field: str, raw_counts: dict):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            "gemini-2.5-flash",
            generation_config={"response_mime_type": "application/json"}
        )
        prompt = f"""You are a CRM Data Visualization expert.
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
# DRILL-DOWN SLICER
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

    st.markdown(
        f'<div class="slice-header {css_extra}">'
        f'<span style="color:{color};font-weight:600;">▶ LEVEL {level}</span>'
        f'&nbsp;&nbsp;<span style="color:#64748b;">{entity}{crumb}</span>'
        f'&nbsp;&nbsp;<span style="color:#94a3b8;font-size:11px;">{len(df):,} records</span>'
        f'</div>',
        unsafe_allow_html=True
    )

    col_sel, col_btn = st.columns([4, 1])
    with col_sel:
        field = st.selectbox(f"Analyze field (Level {level})", analyzable, key=f"field_{uid}")
    with col_btn:
        st.write("")
        st.write("")
        run = st.button("Analyze ▶", key=f"run_{uid}")

    result_key = f"result_{uid}"

    if run:
        raw_counts = {str(k): int(v) for k, v in df[field].astype(str).value_counts().items()}
        with st.spinner(f"Gemini analyzing {field}..."):
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

    # Metrics — use native st.columns instead of custom HTML flex row
    m1, m2, m3 = st.columns(3)
    m1.metric("Records", f"{total:,}")
    m2.metric("Categories", viz_df.shape[0])
    m3.metric(f"Top: {top_cat}", top_pct)

    render_chart(viz_df, field, result.get("graph_type", "Bar Chart"), height=280)

    if result.get("insight"):
        st.info(f"💡 **AI Insight:** {result['insight']}")

    # Drill Down
    if level < 3:
        st.markdown("---")
        st.caption("DRILL INTO A CATEGORY")
        col_d1, col_d2 = st.columns([4, 1])
        with col_d1:
            categories   = sorted(viz_df[field].tolist())
            selected_cat = st.selectbox(
                f"Filter by {field}",
                ["— view all —"] + categories,
                key=f"drill_cat_{uid}"
            )
        with col_d2:
            st.write("")
            st.write("")
            drill_clicked = st.button("Drill ↓", key=f"drill_btn_{uid}")

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
            st.markdown("---")
            render_slicer(drilled_df, entity, gemini_key, level=level + 1, parent_label=new_parent)

# ==========================================
# SESSION STATE
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
    st.markdown("### ⚡ Kylas Intelligence")
    st.caption("CRM Drill-Down Analyzer")
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    st.markdown("**GEMINI API KEY**")
    gemini_input = st.text_input("", type="password",
                                  value=st.session_state.gemini_key,
                                  placeholder="AIza...",
                                  label_visibility="collapsed")
    if st.button("Save Key"):
        if gemini_input:
            st.session_state.gemini_key = gemini_input
            st.session_state.gemini_set = True
            st.success("Saved to session only")
        else:
            st.error("Enter your Gemini API key")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    st.markdown("**DATA SOURCE**")
    entity   = st.selectbox("Module", ENTITY_LIST)
    uploaded = st.file_uploader(f"Upload {entity} CSV", type=["csv"],
                                 help="Export from Kylas → Reports → Export CSV")

    if uploaded:
        try:
            df_up = load_csv(uploaded)
            st.session_state.df     = df_up
            st.session_state.entity = entity
            st.success(f"{len(df_up):,} rows · {len(df_up.columns)} cols")

            with st.expander(f"📋 {len(df_up.columns)} columns detected"):
                analyzable = get_analyzable_cols(df_up)
                st.caption(f"🔬 {len(analyzable)} analyzable · {len(df_up.columns) - len(analyzable)} skipped")
                for c in df_up.columns:
                    nuniq  = df_up[c].astype(str).nunique()
                    is_dup = bool(re.search(r"_\d+$", c))
                    icon   = "🔬" if c in analyzable else ("⚠️" if is_dup else "·")
                    tag    = " (duplicate)" if is_dup else ""
                    st.caption(f"{icon} {c}{tag} · {nuniq} unique")
        except Exception as e:
            st.error(f"CSV read error: {e}")

    with st.expander("📤 How to export from Kylas?"):
        st.markdown("""
1. Open Kylas CRM
2. Go to **Leads / Contacts / Companies / Deals**
3. Top right → **⋮ More** → **Export**
4. Select **All fields** → Download CSV
5. Upload the file above
        """)

# ==========================================
# MAIN TABS
# ==========================================
tab1, tab2, tab3 = st.tabs(["🔬  DRILL-DOWN SLICER", "🗃  DATA TABLE", "🕘  VERSION HISTORY"])

# ── Tab 1: Drill-Down Slicer ──────────────────────────────
with tab1:
    if st.session_state.df is not None and st.session_state.gemini_key:
        ent = st.session_state.entity or entity

        # Header card
        st.markdown(
            f'<div class="intel-card">'
            f'<b style="font-size:16px;">{ent} — Drill-Down Analysis</b>'
            f'&nbsp;&nbsp;<span class="tag tag-blue">L1 Field</span>'
            f'&nbsp;<span class="tag tag-purple">L2 Drill</span>'
            f'&nbsp;<span class="tag tag-amber">L3 Drill</span>'
            f'<div style="color:#64748b;font-size:12px;margin-top:8px;">'
            f'Pick a field → Analyze with Gemini → Drill into any category → Analyze again (max 3 levels)'
            f'</div></div>',
            unsafe_allow_html=True
        )

        render_slicer(
            st.session_state.df,
            ent,
            st.session_state.gemini_key,
            level=1,
            parent_label=""
        )

    else:
        # Native Streamlit get-started guide — no HTML
        gemini_done = bool(st.session_state.gemini_key)
        data_done   = st.session_state.df is not None

        st.write("")
        st.write("")
        _, col_mid, _ = st.columns([1, 2, 1])
        with col_mid:
            st.markdown("#### GET STARTED")
            st.write("")

            if gemini_done:
                st.success("✅ **Step 1 complete** — Gemini API key saved")
            else:
                st.info("**Step 1** — Enter your Gemini API key\n\n*Sidebar → Gemini API Key → Save Key*")

            if data_done:
                st.success("✅ **Step 2 complete** — CSV loaded")
            else:
                st.info("**Step 2** — Upload your Kylas CSV\n\n*Sidebar → Upload CSV → Browse files*")

            if gemini_done and data_done:
                st.info("**Step 3** — Pick a field above and click **Analyze ▶**")
            else:
                st.markdown(
                    "*Step 3 — Pick a field and click Analyze ▶*",
                )

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
        st.markdown(f"**{len(history)} runs saved** — 🔒 API keys never stored")
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

                        hm1, hm2 = st.columns(2)
                        hm1.metric("Records", f"{total_h:,}")
                        hm2.metric("Categories", len(hist_df))

                        render_chart(hist_df, entry["field"], entry.get("graph_type","Bar Chart"), height=220)

                if entry.get("insight"):
                    st.info(f"💡 {entry['insight']}")

                col_a, col_b = st.columns(2)
                with col_a:
                    st.json({"mapping": mapping})
                with col_b:
                    st.json({"raw_counts": raw_counts})
