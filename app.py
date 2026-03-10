import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px
import json
import os
import re
import sqlite3
import subprocess
import sys
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
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; background-color: #0d0f12; color: #e2e8f0; }
.stApp { background-color: #0d0f12; }
[data-testid="stSidebar"] { background-color: #111418 !important; border-right: 1px solid #1e2530; }
.intel-card { background: #151a22; border: 1px solid #1e2b3c; border-radius: 8px; padding: 20px 24px; margin-bottom: 16px; }
.intel-card:hover { border-color: #2a7aff; transition: border-color 0.2s; }
.metric-row { display: flex; gap: 12px; margin-bottom: 20px; }
.metric-box { flex: 1; background: #151a22; border: 1px solid #1e2b3c; border-radius: 6px; padding: 16px; text-align: center; }
.metric-box .val { font-family: 'IBM Plex Mono', monospace; font-size: 28px; font-weight: 600; color: #2a7aff; }
.metric-box .lbl { font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 1px; }
.slice-header { background: #0d1a2d; border: 1px solid #1e3a5f; border-left: 3px solid #2a7aff; border-radius: 6px; padding: 10px 16px; margin: 16px 0 8px 0; font-family: 'IBM Plex Mono', monospace; font-size: 13px; color: #60a5fa; }
.slice-l2 { border-left-color: #8b5cf6 !important; background: #150d2d !important; border-color: #3b1f6b !important; color: #a78bfa !important; }
.slice-l3 { border-left-color: #f59e0b !important; background: #1a1200 !important; border-color: #4a3000 !important; color: #fbbf24 !important; }
h1, h2, h3 { font-family: 'IBM Plex Mono', monospace !important; }
h1 { color: #f1f5f9 !important; font-size: 22px !important; }
.stButton > button { background: #2a7aff !important; color: white !important; border: none !important; border-radius: 4px !important; font-family: 'IBM Plex Mono', monospace !important; font-size: 13px !important; font-weight: 600 !important; padding: 8px 20px !important; width: 100%; }
.stButton > button:hover { background: #1a6aef !important; }
.stTextInput input { background: #151a22 !important; border: 1px solid #1e2b3c !important; color: #e2e8f0 !important; font-family: 'IBM Plex Mono', monospace !important; }
.tag { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 11px; font-family: 'IBM Plex Mono', monospace; font-weight: 600; }
.tag-blue   { background: #1a3a6b; color: #60a5fa; }
.tag-purple { background: #2d1b5e; color: #a78bfa; }
.tag-amber  { background: #3b2a0a; color: #fbbf24; }
.divider { border: none; border-top: 1px solid #1e2530; margin: 20px 0; }
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# CONSTANTS
# ==========================================
HISTORY_FILE = "crm_intelligence_history.json"
DB_FILE      = "kylas_cache.db"
ENTITY_LIST  = ["Leads", "Contacts", "Companies", "Deals"]
EXCLUDE_COLS = {"ID", "Name", "Emails", "Phones", "Created At", "Amount", "Updated At"}
CHART_COLORS = ["#2a7aff","#8b5cf6","#f59e0b","#10b981","#ef4444","#ec4899","#06b6d4","#84cc16"]
LEVEL_COLORS = ["#2a7aff", "#8b5cf6", "#f59e0b"]

# ==========================================
# HISTORY — API KEYS NEVER STORED
# ==========================================
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_to_history(entry: dict):
    # Strip any accidental API key fields before writing to disk
    BANNED_KEYS = {"kylas_key", "gemini_key", "api_key", "key", "token", "secret"}
    safe_entry  = {k: v for k, v in entry.items() if k.lower() not in BANNED_KEYS}
    history = load_history()
    history.insert(0, safe_entry)
    history = history[:100]
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

# ==========================================
# CACHE HELPERS
# ==========================================
def load_from_cache(entity: str) -> list:
    if not os.path.exists(DB_FILE):
        return []
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute("SELECT data FROM records WHERE entity=?", (entity,)).fetchall()
    conn.close()
    return [json.loads(r[0]) for r in rows]

def get_cache_meta() -> dict:
    if not os.path.exists(DB_FILE):
        return {}
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute("SELECT entity, last_sync, total_records FROM sync_meta").fetchall()
    conn.close()
    return {r[0]: {"last_sync": r[1], "total": r[2]} for r in rows}

def trigger_sync(api_key: str, entity: str):
    result = subprocess.run(
        [sys.executable, "kylas_sync.py", "--entity", entity, "--key", api_key],
        capture_output=True, text=True
    )
    return result.stdout + result.stderr

# ==========================================
# DATA FLATTENER (for cache records)
# ==========================================
def _val(node, key="name"):
    return node.get(key) if isinstance(node, dict) else None

def _join_list(items, key="value"):
    if not items: return None
    return ", ".join(str(i.get(key,"")).strip() for i in items if i.get(key))

def _cf_label(k):
    s = re.sub(r'^cf', '', k)
    s = re.sub(r'([A-Z])', r' \1', s)
    return s.strip().title()

def flatten_records(records: list) -> pd.DataFrame:
    flat = []
    for r in records:
        d = {
            "ID":             r.get("id"),
            "Name":           r.get("name") or f"{r.get('firstName','')} {r.get('lastName','')}".strip() or None,
            "Owner":          _val(r.get("ownedBy") or r.get("assignedTo")),
            "Pipeline":       _val(r.get("pipeline")),
            "Pipeline Stage": _val(r.get("pipelineStage")),
            "Industry":       _val(r.get("industry")),
            "Employee Size":  _val(r.get("numberOfEmployees")),
            "Emails":         _join_list(r.get("emails"), "value"),
            "Phones":         _join_list(r.get("phoneNumbers"), "value"),
            "Amount":         r.get("amount"),
            "Created At":     r.get("createdAt","")[:10] if r.get("createdAt") else None,
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

def get_analyzable_cols(df: pd.DataFrame) -> list:
    return [c for c in df.columns if c not in EXCLUDE_COLS and 2 <= df[c].nunique() <= 50]

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
def render_chart(viz_df: pd.DataFrame, field: str, graph_type: str, height: int = 320):
    if viz_df.empty:
        st.info("No data to display.")
        return
    layout = dict(
        paper_bgcolor="#151a22", plot_bgcolor="#151a22",
        font=dict(family="IBM Plex Mono", color="#94a3b8"),
        margin=dict(l=20, r=20, t=30, b=20),
        height=height,
    )
    if "Bar" in graph_type:
        fig = px.bar(viz_df, x=field, y="Count", color=field,
                     color_discrete_sequence=CHART_COLORS, template="plotly_dark")
        fig.update_layout(**layout, showlegend=False,
                          xaxis=dict(gridcolor="#1e2530"),
                          yaxis=dict(gridcolor="#1e2530"))
    else:
        hole = 0.45 if "Donut" in graph_type else 0
        fig  = px.pie(viz_df, values="Count", names=field,
                      color_discrete_sequence=CHART_COLORS, hole=hole, template="plotly_dark")
        fig.update_layout(**layout)
        fig.update_traces(textfont_color="#e2e8f0")
    st.plotly_chart(fig, use_container_width=True)

# ==========================================
# DRILL-DOWN SLICER — recursive, max 3 levels
# ==========================================
def apply_mapping(df: pd.DataFrame, field: str, mapping: dict):
    df   = df.copy()
    col  = f"_std_{field}"
    df[col] = df[field].astype(str).map(mapping).fillna("Other")
    return df, col

def render_slicer(df: pd.DataFrame, entity: str, gemini_key: str,
                  level: int = 1, parent_label: str = ""):
    if df is None or df.empty:
        st.info("No records in this slice.")
        return

    analyzable = get_analyzable_cols(df)
    if not analyzable:
        st.info("No categorical columns available to slice further.")
        return

    color      = LEVEL_COLORS[level - 1]
    css_extra  = f"slice-l{level}" if level > 1 else ""
    breadcrumb = f"  →  {parent_label}" if parent_label else ""
    uid        = f"l{level}_{abs(hash(parent_label)) % 100000}"

    st.markdown(f"""
    <div class="slice-header {css_extra}">
        <span style="color:{color};font-weight:600;">▶ LEVEL {level}</span>&nbsp;&nbsp;
        <span style="color:#94a3b8;">{entity}{breadcrumb}</span>&nbsp;&nbsp;
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
        raw_counts = {str(k): int(v) for k, v in df[field].value_counts().items()}
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

    render_chart(viz_df, field, result.get("graph_type","Bar Chart"), height=280)

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
        st.markdown(f"""
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

            next_color = LEVEL_COLORS[level]   # color for next level
            st.markdown(f"<div style='margin-top:8px;padding-left:16px;border-left:2px solid {next_color}33;'>",
                        unsafe_allow_html=True)
            render_slicer(drilled_df, entity, gemini_key, level=level + 1, parent_label=new_parent)
            st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# SESSION STATE INIT
# ==========================================
for key, default in [
    ("kylas_key", ""), ("gemini_key", ""),
    ("keys_set", False), ("df", None), ("entity", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.markdown("### ⚡ KYLAS INTELLIGENCE")
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── API Keys ──────────────────────────
    st.markdown("**API CONFIGURATION**")
    kylas_input  = st.text_input("Kylas API Key",  type="password",
                                  value=st.session_state.kylas_key, placeholder="xxxx:xxxxx")
    gemini_input = st.text_input("Gemini API Key", type="password",
                                  value=st.session_state.gemini_key, placeholder="AIza...")

    if st.button("Save Keys"):
        if kylas_input and gemini_input:
            st.session_state.kylas_key  = kylas_input
            st.session_state.gemini_key = gemini_input
            st.session_state.keys_set   = True
            st.success("✅ Saved to session only — never written to disk")
        else:
            st.error("Both keys required")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── Data Source ────────────────────────
    st.markdown("**DATA SOURCE**")
    entity      = st.selectbox("Module", ENTITY_LIST)
    source_mode = st.radio("Load from", ["📁 Upload CSV", "🗄 Kylas Cache"], horizontal=True)

    # ── MODE 1: CSV Upload ─────────────────
    if source_mode == "📁 Upload CSV":
        st.markdown("""
        <div style="font-size:11px;color:#64748b;font-family:'IBM Plex Mono';margin-bottom:8px;">
            Export CSV from Kylas → upload here.<br>No API call needed.
        </div>
        """, unsafe_allow_html=True)

        uploaded = st.file_uploader(f"Upload {entity} CSV", type=["csv"])

        if uploaded:
            try:
                df_up = pd.read_csv(uploaded, dtype=str).fillna("")
                # Auto-rename common Kylas export headers
                rename_map = {}
                for col in df_up.columns:
                    low = col.lower().strip()
                    if low in ("id","lead id","contact id","company id","deal id"):
                        rename_map[col] = "ID"
                    elif low in ("name","full name","company name","lead name","contact name"):
                        rename_map[col] = "Name"
                    elif "employee" in low:
                        rename_map[col] = "Employee Size"
                    elif "industry" in low:
                        rename_map[col] = "Industry"
                    elif "pipeline stage" in low:
                        rename_map[col] = "Pipeline Stage"
                    elif "owner" in low:
                        rename_map[col] = "Owner"
                if rename_map:
                    df_up.rename(columns=rename_map, inplace=True)

                st.session_state.df     = df_up
                st.session_state.entity = entity
                st.success(f"✅ {len(df_up):,} rows loaded")

                with st.expander("Columns detected"):
                    st.write(list(df_up.columns))
            except Exception as e:
                st.error(f"Error reading CSV: {e}")

    # ── MODE 2: Kylas Cache ─────────────────
    else:
        cache_meta = get_cache_meta()
        if entity in cache_meta:
            m    = cache_meta[entity]
            last = m["last_sync"][:16].replace("T"," ") if m.get("last_sync") else "never"
            st.markdown(f"""
            <div style="background:#0d2137;border:1px solid #1e3a5f;border-radius:4px;
                        padding:10px 12px;margin-bottom:8px;">
                <span style="font-family:'IBM Plex Mono';font-size:11px;color:#60a5fa;">
                    CACHE: {m['total']:,} records<br>Last sync: {last}
                </span>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background:#1a0f0f;border:1px solid #5f1e1e;border-radius:4px;
                        padding:10px 12px;margin-bottom:8px;">
                <span style="font-family:'IBM Plex Mono';font-size:11px;color:#f87171;">
                    NO CACHE — run: python kylas_sync.py --full
                </span>
            </div>""", unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("⚡ Load"):
                recs = load_from_cache(entity)
                if recs:
                    st.session_state.df     = flatten_records(recs)
                    st.session_state.entity = entity
                    st.success(f"✅ {len(recs):,} loaded")
                else:
                    st.error("Cache empty")
        with c2:
            if st.button("🔄 Sync"):
                if not st.session_state.keys_set:
                    st.error("Save keys first")
                else:
                    with st.spinner("Syncing..."):
                        trigger_sync(st.session_state.kylas_key, entity)
                    recs = load_from_cache(entity)
                    if recs:
                        st.session_state.df     = flatten_records(recs)
                        st.session_state.entity = entity
                        st.success("Done!")

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

    elif st.session_state.df is None:
        st.markdown("""
        <div style="text-align:center;padding:80px 0;color:#334155;">
            <div style="font-size:48px;margin-bottom:16px;">⚡</div>
            <div style="font-family:'IBM Plex Mono';font-size:15px;color:#1e3a5f;">
                Upload a CSV or load from cache to begin
            </div>
            <div style="font-family:'IBM Plex Mono';font-size:12px;color:#0f1f35;margin-top:8px;">
                Sidebar → Data Source → Upload CSV
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("Save your Gemini API key in the sidebar to enable analysis.")

# ── Tab 2: Data Table ─────────────────────────────────────
with tab2:
    if st.session_state.df is not None:
        df  = st.session_state.df
        ent = st.session_state.entity or "Data"
        st.markdown(f"**{ent}** — {len(df):,} records, {len(df.columns)} columns")

        show_cols = st.multiselect(
            "Columns to show",
            df.columns.tolist(),
            default=df.columns.tolist()[:12]
        )
        if show_cols:
            st.dataframe(df[show_cols], use_container_width=True, height=500)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇ Download CSV", csv, f"{ent}_kylas.csv", "text/csv")
    else:
        st.info("Load data first from the sidebar.")

# ── Tab 3: Version History ────────────────────────────────
with tab3:
    history = load_history()

    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.markdown(f"**{len(history)} runs saved** &nbsp;·&nbsp; "
                    f"<span style='color:#4ade80;font-size:12px;'>🔒 API keys never stored</span>",
                    unsafe_allow_html=True)
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
                          f"|  L{level}  |  {entry.get('graph_type','')}")

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
                            <div class="metric-box" style="background:#151a22;border:1px solid #1e2b3c;
                                border-radius:6px;padding:12px;text-align:center;flex:1;">
                                <div style="font-family:'IBM Plex Mono';font-size:22px;font-weight:600;color:{color};">{total_h:,}</div>
                                <div style="font-size:10px;color:#64748b;">RECORDS</div>
                            </div>
                            <div class="metric-box" style="background:#151a22;border:1px solid #1e2b3c;
                                border-radius:6px;padding:12px;text-align:center;flex:1;">
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
