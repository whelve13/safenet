import streamlit as st
import pandas as pd
import sqlite3
import sys
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
from datetime import datetime

# ── Path setup ──────────────────────────────────────────────────────────────
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT_DIR)

from src.models.config import AnalysisConfig
from src.database.repository import DatabaseRepository
from src.reports.report_generator import ReportGenerator
from src.services.pipeline_service import process_uploaded_file_bytes

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SafeNet",
    layout="wide",
    initial_sidebar_state="expanded",
)

def inject_custom_css():
    st.markdown("""
    <style>
        /* Modern SaaS aesthetic */
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
        
        html, body, [class*="css"]  {
            font-family: 'Plus Jakarta Sans', sans-serif;
        }
        
        /* Main background */
        .stApp {
            background-color: #f8fafc;
        }
        
        /* Sidebar styling */
        [data-testid="stSidebar"] {
            background-color: #ffffff;
            border-right: 1px solid #e2e8f0;
        }
        [data-testid="stSidebar"] > div:first-child {
            display: flex;
            flex-direction: column;
            height: 100%;
        }
        
        /* Remove top padding and restrict max-width for better horizontal balance */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 1200px;
        }

        /* Metric Cards & Generic Cards */
        .card-bg {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
        }

        .metric-card {
            padding: 20px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        
        .metric-label {
            font-size: 12px;
            color: #64748b;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        .metric-value {
            font-size: 28px;
            font-weight: 700;
            color: #0f172a;
        }

        /* Expander styling */
        .streamlit-expanderHeader {
            font-weight: 500 !important;
            color: #475569 !important;
            background-color: transparent !important;
            border-radius: 6px !important;
            padding: 8px 12px !important;
        }
        .streamlit-expanderHeader:hover {
            background-color: #f1f5f9 !important;
            color: #0f172a !important;
        }
        .streamlit-expanderContent {
            border: none;
            padding-left: 12px;
            padding-right: 12px;
        }

        /* Tabs styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 24px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: transparent;
            border-radius: 0px 0px 0px 0px;
            gap: 1px;
            padding-top: 10px;
            padding-bottom: 10px;
            font-weight: 500;
        }
        
        /* Custom SVGs and Typography */
        h1, h2, h3, h4, h5, h6 {
            color: #0f172a;
            font-weight: 600;
        }

        .text-primary { color: #0f172a; }
        .text-secondary { color: #475569; }
        .border-bottom { border-bottom: 1px solid #e2e8f0; }

        /* Buttons */
        .stButton>button {
            border-radius: 6px;
            font-weight: 500;
            border: 1px solid #e2e8f0;
            background-color: #ffffff;
            color: #0f172a;
            transition: all 0.2s ease;
        }
        .stButton>button[kind="primary"] {
            background-color: #2563eb;
            color: white;
            border: none;
            font-weight: 600;
            box-shadow: 0 1px 3px rgba(37, 99, 235, 0.3);
        }
        .stButton>button[kind="primary"]:hover {
            background-color: #1d4ed8;
        }
        
        /* Alerts / Badges */
        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.02em;
        }
        .badge-critical { background-color: #fee2e2; color: #991b1b; }
        .badge-high { background-color: #fef3c7; color: #92400e; }
        .badge-medium { background-color: #fef08a; color: #854d0e; }
        .badge-low { background-color: #dcfce7; color: #166534; }
        
        .risk-badge {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .risk-high { background-color: #ef4444; }
        .risk-medium { background-color: #f97316; }
        .risk-low { background-color: #10b981; }

        /* Custom File Uploader styling */
        [data-testid="stFileUploader"] {
            padding: 0 !important;
            background-color: transparent !important;
            width: 100%;
        }
        [data-testid="stFileUploaderDropzone"] {
            border: 1px solid #e2e8f0;
            background-color: #f8fafc;
            border-radius: 6px;
            padding: 8px 12px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        [data-testid="stFileUploaderDropzone"]:hover {
            border-color: #cbd5e1;
            background-color: #f1f5f9;
        }
        /* Hide the bulky cloud SVG */
        [data-testid="stFileUploaderDropzone"] svg {
            display: none;
        }
        /* Style the instructions */
        [data-testid="stFileUploaderDropzoneInstructions"] > div {
            font-size: 12px !important;
            color: #64748b !important;
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            margin-bottom: 0px !important;
        }
        /* Style the "Browse files" button inside uploader */
        [data-testid="stFileUploaderDropzone"] button {
            border: 1px solid #e2e8f0;
            background-color: #ffffff;
            color: #0f172a;
            border-radius: 4px;
            font-size: 12px;
            padding: 2px 8px;
            margin-top: 4px;
            width: 100%;
            font-weight: 500;
        }
        /* Style the uploaded file row */
        [data-testid="stUploadedFile"] {
            background-color: #f8fafc;
            border-radius: 4px;
            padding: 6px 10px;
            margin-top: 6px;
            border: 1px solid #e2e8f0;
        }
        [data-testid="stUploadedFile"] div[data-testid="stText"] {
            font-size: 12px !important;
            color: #0f172a !important;
        }

        /* Dashboard Focal Point */
        .focal-card {
            background-color: #ffffff;
            border-left: 4px solid #2563eb;
            border-radius: 8px;
            padding: 16px 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            margin-bottom: 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        /* Metric card emphasis */
        .metric-card-critical {
            border: 1px solid #fca5a5 !important;
            background-color: #fef2f2 !important;
        }
        .metric-card-critical .metric-label {
            color: #b91c1c !important;
        }
        .metric-card-critical .metric-value {
            color: #991b1b !important;
        }

        /* Dark mode overrides */
        @media (prefers-color-scheme: dark) {
            .stApp { background-color: #0b0f19; }
            [data-testid="stSidebar"] { background-color: #111827; border-right: 1px solid #1f2937; }
            .card-bg { background-color: #1f2937 !important; border-color: #374151 !important; }
            .metric-label { color: #9ca3af; }
            .metric-value { color: #f9fafb; }
            h1, h2, h3, h4, h5, h6 { color: #f9fafb; }
            .stButton>button { background-color: #1f2937; border-color: #374151; color: #f9fafb; }
            p, span, div { color: #d1d5db; }
            .text-primary { color: #f9fafb !important; }
            .text-secondary { color: #9ca3af !important; }
            .border-bottom { border-bottom: 1px solid #374151 !important; }
            
            .streamlit-expanderHeader { color: #9ca3af !important; }
            .streamlit-expanderHeader:hover { background-color: #1f2937 !important; color: #f9fafb !important; }
            
            [data-testid="stFileUploaderDropzone"] { border-color: #374151; background-color: #111827; }
            [data-testid="stFileUploaderDropzone"]:hover { border-color: #4b5563; background-color: #1f2937; }
            [data-testid="stFileUploaderDropzoneInstructions"] > div { color: #9ca3af !important; }
            [data-testid="stFileUploaderDropzone"] button { background-color: #1f2937; border-color: #374151; color: #f9fafb; }
            [data-testid="stUploadedFile"] { background-color: #1f2937; border-color: #374151; }

            .badge-critical { background-color: rgba(153, 27, 27, 0.4); color: #fca5a5; }
            .badge-high { background-color: rgba(146, 64, 14, 0.4); color: #fcd34d; }
            .badge-medium { background-color: rgba(133, 77, 14, 0.4); color: #fde047; }
            .badge-low { background-color: rgba(22, 101, 52, 0.4); color: #86efac; }
            
            .focal-card { background-color: #1f2937; border-left: 4px solid #3b82f6; box-shadow: none; }
            .metric-card-critical { background-color: rgba(153, 27, 27, 0.1) !important; border-color: rgba(248, 113, 113, 0.4) !important; }
            .metric-card-critical .metric-label { color: #fca5a5 !important; }
            .metric-card-critical .metric-value { color: #fef2f2 !important; }
        }
    </style>
    """, unsafe_allow_html=True)

def get_svg_icon(name, color="currentColor", size=20):
    icons = {
        "shield": f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>''',
        "chart": f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>''',
        "alert": f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>''',
        "network": f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>''',
        "users": f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>''',
        "target": f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><circle cx="12" cy="12" r="6"></circle><circle cx="12" cy="12" r="2"></circle></svg>''',
        "document": f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>''',
        "database": f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path></svg>'''
    }
    return icons.get(name, "")

inject_custom_css()

# ── State Management ────────────────────────────────────────────────────────
if 'analysis_status' not in st.session_state:
    st.session_state.analysis_status = 'empty'  # 'empty', 'ready', 'complete'
if 'current_file_name' not in st.session_state:
    st.session_state.current_file_name = None
if 'last_scan_error' not in st.session_state:
    st.session_state.last_scan_error = None
if 'sample_mode' not in st.session_state:
    st.session_state.sample_mode = False
if 'sample_autorun_attempted' not in st.session_state:
    st.session_state.sample_autorun_attempted = False

# ── Helpers ─────────────────────────────────────────────────────────────────
DB_PATH = os.path.join(ROOT_DIR, "safenet.db")
SAMPLE_CHAT_PATH = os.path.join(ROOT_DIR, "data", "sample.txt")

def format_timestamp(ts_str):
    if not ts_str:
        return ""
    try:
        dt = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        now = datetime.now(dt.tzinfo if dt.tzinfo else None)
        if dt.date() == now.date():
            return f"Today • {dt.strftime('%H:%M')}"
        elif (now.date() - dt.date()).days == 1:
            return f"Yesterday • {dt.strftime('%H:%M')}"
        else:
            return f"{dt.strftime('%b %-d')} • {dt.strftime('%H:%M')}"
    except Exception:
        return str(ts_str)[:16]

@st.cache_resource
def get_repo() -> DatabaseRepository:
    return DatabaseRepository(DB_PATH)

def parse_weighted_lines(raw_input: str, default_weight: float, field_name: str) -> dict[str, float]:
    parsed: dict[str, float] = {}
    for line_number, line in enumerate(raw_input.strip().split("\n"), start=1):
        line = line.strip()
        if not line:
            continue

        parts = line.split(",")
        phrase = parts[0].strip().lower()
        if not phrase:
            continue

        if len(parts) > 1:
            try:
                weight = float(parts[1].strip())
            except ValueError as exc:
                raise ValueError(f"Invalid weight in {field_name} line {line_number}: '{line}'") from exc
        else:
            weight = default_weight

        parsed[phrase] = weight
    return parsed

def build_config_from_session() -> AnalysisConfig:
    # reads the current settings from session_state and builds a config
    custom_words = parse_weighted_lines(
        st.session_state.get("cfg_custom_words", ""),
        default_weight=0.7,
        field_name="Custom Keywords",
    )
    custom_phrases = parse_weighted_lines(
        st.session_state.get("cfg_custom_phrases", ""),
        default_weight=0.9,
        field_name="Custom Phrases",
    )

    return AnalysisConfig(
        toxicity_threshold=st.session_state.get("cfg_threshold", 0.7),
        escalation_window_size=st.session_state.get("cfg_window", 5),
        escalation_sensitivity=st.session_state.get("cfg_sensitivity", 0.3),
        min_gang_up_aggressors=st.session_state.get("cfg_gangup", 2),
        high_risk_floor=st.session_state.get("cfg_risk_floor", 0.3),
        custom_toxic_words=custom_words,
        custom_toxic_phrases=custom_phrases,
        use_hf_model=st.session_state.get("cfg_use_hf", True),
        hf_fallback_threshold=st.session_state.get("cfg_hf_threshold", 0.8),
        hf_batch_size=st.session_state.get("cfg_hf_batch_size", 16),
        hf_max_length=st.session_state.get("cfg_hf_max_length", 128),
        hf_device=st.session_state.get("cfg_hf_device", -1),
    )

def run_pipeline(file_bytes: bytes, filename: str, repo: DatabaseRepository, config: AnalysisConfig):
    # runs the full SafeNet analysis pipeline on uploaded file bytes
    return process_uploaded_file_bytes(file_bytes, filename, repo, config)

def execute_scan(repo: DatabaseRepository, file_bytes: bytes, filename: str):
    config = build_config_from_session()
    with st.spinner("Analyzing conversation..."):
        run_pipeline(file_bytes, filename, repo, config)

    st.session_state.analysis_status = 'complete'
    st.session_state.current_file_name = filename
    st.session_state.last_scan_error = None
    if 'pdf_ready' in st.session_state:
        del st.session_state['pdf_ready']
    st.rerun()

def maybe_autorun_sample(repo: DatabaseRepository):
    if st.session_state.sample_autorun_attempted:
        return

    st.session_state.sample_autorun_attempted = True
    if st.session_state.analysis_status != 'empty' or repo.has_data() or not os.path.exists(SAMPLE_CHAT_PATH):
        return

    try:
        with open(SAMPLE_CHAT_PATH, 'rb') as sample_file:
            st.session_state.sample_mode = True
            execute_scan(repo, sample_file.read(), os.path.basename(SAMPLE_CHAT_PATH))
    except Exception as exc:
        st.session_state.sample_mode = False
        st.session_state.last_scan_error = f"Automatic sample scan failed: {exc}"

def load_dataframes(repo: DatabaseRepository):
    # loads core dataframes from SQLite
    conn = sqlite3.connect(repo.db_path, check_same_thread=False)
    users_df = pd.read_sql_query("SELECT * FROM users ORDER BY risk_score DESC", conn)
    alerts_df = pd.read_sql_query("SELECT * FROM alerts ORDER BY timestamp DESC", conn)
    messages_df = pd.read_sql_query("SELECT * FROM messages ORDER BY timestamp ASC", conn)
    conn.close()
    return users_df, alerts_df, messages_df


def render_extension_audit_tab(repo: DatabaseRepository):
    st.markdown("<h4 class='text-primary'>Live Moderation Audit</h4>", unsafe_allow_html=True)
    st.markdown(
        "<p class='text-secondary' style='font-size: 14px;'>Recorded API/extension moderation events from real detections.</p>",
        unsafe_allow_html=True,
    )

    events = repo.get_moderation_events(limit=500)
    if not events:
        st.info("No extension/API moderation events have been recorded yet.")
        return

    events_df = pd.DataFrame(
        events,
        columns=[
            "id",
            "timestamp",
            "source",
            "page_url",
            "page_domain",
            "snippet",
            "toxicity_score",
            "severity",
            "decision",
            "detection_method",
            "explanation",
        ],
    )

    severity_filter = st.selectbox(
        "Filter extension events by severity",
        ["All", "low", "medium", "high", "critical"],
        key="extension_audit_severity_filter",
        label_visibility="collapsed",
    )
    filtered_df = events_df if severity_filter == "All" else events_df[events_df["severity"] == severity_filter]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Recorded events", len(filtered_df))
    m2.metric("Blur actions", int((filtered_df["decision"] == "blur").sum()))
    m3.metric("Block actions", int((filtered_df["decision"] == "block").sum()))
    m4.metric("Critical", int((filtered_df["severity"] == "critical").sum()))

    view_df = filtered_df[
        [
            "timestamp",
            "source",
            "page_domain",
            "page_url",
            "snippet",
            "toxicity_score",
            "severity",
            "decision",
            "detection_method",
            "explanation",
        ]
    ].copy()
    view_df["toxicity_score"] = view_df["toxicity_score"].map(lambda x: f"{float(x):.2f}")
    st.dataframe(view_df, use_container_width=True, height=420)

# ── Initialize ──────────────────────────────────────────────────────────────
repo = get_repo()
maybe_autorun_sample(repo)

# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    # header area
    st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 24px; padding-top: 4px;">
            {get_svg_icon('shield', size=26, color='#3b82f6')}
            <h2 class="text-primary" style="margin: 0; font-size: 20px; font-weight: 800; letter-spacing: -0.03em;">SafeNet</h2>
        </div>
    """, unsafe_allow_html=True)

    # 2. Upload Section
    st.markdown("<strong class='text-secondary' style='font-size: 12px; font-weight: 600; margin-bottom: 6px; display: block;'>Upload conversation</strong>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "Upload chat log",
        type=["txt", "json"],
        label_visibility="collapsed"
    )

    # state management logic based on upload
    if uploaded_file is None:
        if st.session_state.analysis_status == 'ready':
            st.session_state.analysis_status = 'empty'
            st.session_state.current_file_name = None
            st.session_state.sample_mode = False
            repo.clear_all_data()
    else:
        if uploaded_file.name != st.session_state.current_file_name:
            st.session_state.current_file_name = uploaded_file.name
            st.session_state.analysis_status = 'ready'
            st.session_state.sample_mode = False
            st.session_state.last_scan_error = None
            repo.clear_all_data()

    st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)

    # actions section
    if st.session_state.analysis_status == 'ready':
        if uploaded_file is not None and st.button("Run scan", use_container_width=True, type="primary"):
            try:
                execute_scan(repo, uploaded_file.getvalue(), uploaded_file.name)
            except Exception as exc:
                st.session_state.last_scan_error = f"Scan failed for {uploaded_file.name}: {exc}"
    elif st.session_state.analysis_status == 'complete':
        has_scan_source = uploaded_file is not None or (st.session_state.sample_mode and os.path.exists(SAMPLE_CHAT_PATH))
        rerun_label = "Run sample scan" if st.session_state.sample_mode else "Run scan"
        if has_scan_source and st.button(rerun_label, use_container_width=True):
            try:
                if uploaded_file is not None:
                    execute_scan(repo, uploaded_file.getvalue(), uploaded_file.name)
                elif st.session_state.sample_mode and os.path.exists(SAMPLE_CHAT_PATH):
                    with open(SAMPLE_CHAT_PATH, 'rb') as sample_file:
                        execute_scan(repo, sample_file.read(), os.path.basename(SAMPLE_CHAT_PATH))
            except Exception as exc:
                source_name = uploaded_file.name if uploaded_file is not None else os.path.basename(SAMPLE_CHAT_PATH)
                st.session_state.last_scan_error = f"Scan failed for {source_name}: {exc}"

    st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)

    # settings section
    with st.expander("Analysis Settings", expanded=False):
        st.slider(
            "Concern Threshold",
            min_value=0.3, max_value=1.0, value=0.7, step=0.05,
            key="cfg_threshold",
            help="Messages scoring at or above this value will be flagged.",
        )
        st.slider(
            "Tracking Window",
            min_value=3, max_value=15, value=5, step=1,
            key="cfg_window",
            help="Number of recent messages to analyze for behavioral trends.",
        )
        st.slider(
            "Sensitivity",
            min_value=0.1, max_value=0.8, value=0.3, step=0.05,
            key="cfg_sensitivity",
            help="Minimum score increase between window halves to trigger a warning.",
        )
        st.number_input(
            "Group Targeting Threshold",
            min_value=2, max_value=10, value=2, step=1,
            key="cfg_gangup",
            help="Minimum distinct senders targeting one person to flag as group targeting.",
        )
        st.slider(
            "High-Risk Baseline",
            min_value=0.1, max_value=0.8, value=0.3, step=0.05,
            key="cfg_risk_floor",
            help="Users with concern scores above this will be prioritized.",
        )
        st.text_area(
            "Custom Keywords",
            placeholder="word, 0.6",
            key="cfg_custom_words",
            help="One per line: `word, weight`.",
            height=80,
        )
        st.text_area(
            "Custom Phrases",
            placeholder="go away, 0.8",
            key="cfg_custom_phrases",
            help="One per line: `phrase, weight`.",
            height=80,
        )
        st.markdown("**Hugging Face Settings**")
        st.checkbox(
            "Enable Hugging Face fallback",
            value=True,
            key="cfg_use_hf",
            help="Use the HF model when dictionary confidence is low.",
        )
        st.slider(
            "HF fallback threshold",
            min_value=0.0, max_value=1.0, value=0.8, step=0.05,
            key="cfg_hf_threshold",
            help="Run HF when dictionary score is below this value.",
        )
        st.slider(
            "HF batch size",
            min_value=1, max_value=64, value=16, step=1,
            key="cfg_hf_batch_size",
            help="Number of messages sent per HF inference call.",
        )
        st.slider(
            "HF max token length",
            min_value=32, max_value=512, value=128, step=16,
            key="cfg_hf_max_length",
            help="Maximum token length used by the HF model.",
        )
        st.number_input(
            "HF device (-1 CPU, 0+ GPU)",
            min_value=-1, max_value=8, value=-1, step=1,
            key="cfg_hf_device",
            help="Set -1 for CPU or a CUDA device index for GPU.",
        )
        st.caption("Adjustments apply on the next scan.")

    # footer section
    # uses margin-top - auto to pin to the bottom
    st.markdown("""
        <div style="margin-top: auto; padding-top: 32px;">
            <p style="color: #9ca3af; font-size: 11px; margin: 0; font-weight: 500;">SafeNet v1.0</p>
        </div>
    """, unsafe_allow_html=True)


# ── Main Content ────────────────────────────────────────────────────────────
if st.session_state.last_scan_error:
    st.error(st.session_state.last_scan_error)

if st.session_state.analysis_status == 'empty':
    tab_manual, tab_extension_audit = st.tabs(["Manual File Analysis", "Extension Audit"])
    with tab_manual:
        st.markdown("<div style='height: 10vh;'></div>", unsafe_allow_html=True)
        _, center, _ = st.columns([1, 1.5, 1])
        with center:
            st.markdown(f"""
            <div class="card-bg" style="padding: 32px; text-align: center; border-radius: 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                <div style="display: flex; justify-content: center; margin-bottom: 16px;">
                    <div style="border: 1px solid #e2e8f0; background-color: #ffffff; padding: 12px; border-radius: 50%;">
                        {get_svg_icon('document', size=24, color='#64748b')}
                    </div>
                </div>
                <h3 class="text-primary" style="margin-bottom: 4px; font-size: 18px;">Upload a conversation to scan for harmful interactions and warning signs.</h3>
                <p class="text-secondary" style="font-size: 13px; font-weight: 500; margin-top: 8px;">
                    Supported formats: .txt, .json
                </p>
            </div>
            """, unsafe_allow_html=True)
    with tab_extension_audit:
        render_extension_audit_tab(repo)
    st.stop()

if st.session_state.analysis_status == 'ready':
    tab_manual, tab_extension_audit = st.tabs(["Manual File Analysis", "Extension Audit"])
    with tab_manual:
        st.markdown("<div style='height: 10vh;'></div>", unsafe_allow_html=True)
        _, center, _ = st.columns([1, 1.5, 1])
        with center:
            st.markdown(f"""
            <div class="card-bg" style="padding: 32px; text-align: center; border-radius: 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                <div style="display: flex; justify-content: center; margin-bottom: 16px;">
                    <div style="border: 1px solid #bfdbfe; background-color: #eff6ff; padding: 12px; border-radius: 50%;">
                        {get_svg_icon('shield', size=24, color='#3b82f6')}
                    </div>
                </div>
                <h3 class="text-primary" style="margin-bottom: 4px; font-size: 18px;">File loaded successfully</h3>
                <p class="text-secondary" style="font-size: 14px; margin-bottom: 0;">
                    Click <strong>Run scan</strong> in the sidebar to begin the analysis.
                </p>
            </div>
            """, unsafe_allow_html=True)
    with tab_extension_audit:
        render_extension_audit_tab(repo)
    st.stop()

# Dashboard State
if st.session_state.analysis_status == 'complete' and not repo.has_data():
    # edge case - scan yielded literally nothing or failed quietly
    st.error("Analysis completed but no data was extracted. Please verify the file format.")
    st.stop()

# ── Load Data ───────────────────────────────────────────────────────────────
users_df, alerts_df, messages_df = load_dataframes(repo)
stats = repo.get_summary_stats()

# ── Focal Anchor ────────────────────────────────────────────────────────────
from src.algorithms.hf_toxicity_model import ML_AVAILABLE
hf_enabled = st.session_state.get("cfg_use_hf", True)
mode_text = "Hybrid (Hugging Face + Dictionary)" if hf_enabled and ML_AVAILABLE else "Dictionary Only"
ml_status = "Available & Loaded" if ML_AVAILABLE else "Unavailable (Missing Dependencies)"

if st.session_state.sample_mode:
    st.info("Loaded bundled sample conversation automatically. Upload your own file in the sidebar to replace it.")

st.markdown(f"""
<div class="focal-card">
    <div>
        <h3 class="text-primary" style="margin: 0 0 4px 0; font-size: 16px;">Analysis Complete</h3>
        <p class="text-secondary" style="margin: 0; font-size: 14px;">The conversation from <strong>{st.session_state.current_file_name}</strong> has been successfully processed.</p>
        <p style="margin: 6px 0 0 0; font-size: 13px; color: #64748b;">
            Detection Mode: <strong style="color: #3b82f6;">{mode_text}</strong> • ML Engine: <strong>{ml_status}</strong>
        </p>
    </div>
    <div style="background-color: #dbeafe; padding: 6px 12px; border-radius: 9999px;">
        <span style="color: #1e3a8a; font-size: 12px; font-weight: 600;">{stats['total_messages']:,} messages processed</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Header Metrics ──────────────────────────────────────────────────────────
st.markdown(f"""
<div style="display: flex; gap: 1rem; margin-bottom: 2rem; flex-wrap: wrap;">
    <div class="metric-card card-bg" style="flex: 1; min-width: 150px;">
        <span class="metric-label">Concerning messages</span>
        <span class="metric-value">{stats['flagged_messages']:,}</span>
    </div>
    <div class="metric-card card-bg" style="flex: 1; min-width: 150px;">
        <span class="metric-label">People involved</span>
        <span class="metric-value">{stats['total_users']:,}</span>
    </div>
    <div class="metric-card card-bg" style="flex: 1; min-width: 150px;">
        <span class="metric-label">Warning signs</span>
        <span class="metric-value">{stats['total_alerts']:,}</span>
    </div>
    <div class="metric-card card-bg metric-card-critical" style="flex: 1; min-width: 150px;">
        <span class="metric-label">Critical concerns</span>
        <span class="metric-value">{stats['critical_alerts']:,}</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Tabs ────────────────────────────────────────────────────────────────────
tab_overview, tab_alerts, tab_graph, tab_users, tab_victims, tab_reports, tab_data, tab_extension_audit = st.tabs([
    "Overview",
    "Warning Signs",
    "Interaction Network",
    "User Profiles",
    "Targeted Individuals",
    "Export Reports",
    "Raw Data",
    "Extension Audit",
])


# OVERVIEW TAB
with tab_overview:
    col_chart, col_risk = st.columns([3, 2])

    with col_chart:
        st.markdown("<h4 class='text-primary'>Conversation timeline</h4>", unsafe_allow_html=True)
        st.markdown("<p class='text-secondary' style='font-size: 14px;'>Tracking language severity over the course of the chat.</p>", unsafe_allow_html=True)
        if not messages_df.empty:
            chart_df = messages_df[['timestamp', 'toxicity_score']].copy()
            chart_df['msg_index'] = range(1, len(chart_df) + 1)

            fig, ax = plt.subplots(figsize=(10, 4.5))
            fig.patch.set_facecolor('none')
            ax.set_facecolor('none')

            colors = ['#ef4444' if s >= 0.7 else '#f97316' if s >= 0.4 else '#10b981' for s in chart_df['toxicity_score']]
            ax.bar(chart_df['msg_index'], chart_df['toxicity_score'], color=colors, width=0.7)
            ax.axhline(y=0.7, color='#ef4444', linestyle='--', linewidth=1.2, alpha=0.5, label='Concern threshold')
            ax.legend(loc='upper left', fontsize=9, frameon=False, labelcolor='#64748b')
            ax.set_xlabel('Message timeline', fontsize=10, color='#64748b')
            ax.set_ylabel('Severity score', fontsize=10, color='#64748b')
            ax.set_ylim(0, 1.05)
            ax.tick_params(colors='#9ca3af', labelsize=9)
            
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color('#4b5563')
            ax.spines['bottom'].set_color('#4b5563')
            
            plt.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

    with col_risk:
        st.markdown("<h4 class='text-primary'>Individuals needing attention</h4>", unsafe_allow_html=True)
        st.markdown("<p class='text-secondary' style='font-size: 14px;'>Users with the most concerning activity.</p>", unsafe_allow_html=True)
        risky = users_df[users_df['risk_score'] > 0].head(8)
        if not risky.empty:
            for _, row in risky.iterrows():
                risk_level = "high" if row['risk_score'] >= 0.7 else "medium" if row['risk_score'] >= 0.3 else "low"
                
                st.markdown(f"""
                <div class="border-bottom" style="padding: 12px; display: flex; align-items: center; justify-content: space-between;">
                    <div style="display: flex; align-items: center;">
                        <span class="risk-badge risk-{risk_level}"></span>
                        <strong class="text-primary" style="margin-right: 8px;">{row['username']}</strong>
                        <span class="text-secondary" style="font-size: 14px;">{row['flagged_messages_count']} concerning messages</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("No concerning behavior detected.")

    # Severity distribution
    if not alerts_df.empty:
        st.markdown("<h4 class='text-primary' style='margin-top: 32px;'>Warning summary</h4>", unsafe_allow_html=True)
        sev_counts = alerts_df['severity'].value_counts()
        sev_colors = {'CRITICAL': '#ef4444', 'HIGH': '#f97316', 'MEDIUM': '#facc15', 'LOW': '#10b981'}

        col_pie, col_info = st.columns([1, 2])
        with col_pie:
            fig2, ax2 = plt.subplots(figsize=(4, 4))
            fig2.patch.set_facecolor('none')
            ax2.pie(
                sev_counts.values,
                labels=sev_counts.index,
                colors=[sev_colors.get(s, '#94a3b8') for s in sev_counts.index],
                autopct='%1.0f%%',
                startangle=140,
                textprops={'color': '#6b7280', 'fontsize': 10, 'fontweight': '600'},
            )
            plt.tight_layout()
            st.pyplot(fig2)
            plt.close(fig2)

        with col_info:
            for sev, count in sev_counts.items():
                badge_class = f"badge-{sev.lower()}"
                st.markdown(f"""
                <div style="margin-bottom: 12px; display: flex; align-items: center;">
                    <span class="badge {badge_class}" style="width: 80px; text-align: center;">{sev}</span>
                    <span class="text-secondary" style="margin-left: 12px;">{count} warning(s)</span>
                </div>
                """, unsafe_allow_html=True)


# ALERTS TAB
with tab_alerts:
    st.markdown("<h4 class='text-primary'>Warning signs</h4>", unsafe_allow_html=True)
    st.markdown("<p class='text-secondary' style='font-size: 14px;'>A log of concerning interactions and potential risks.</p>", unsafe_allow_html=True)

    if alerts_df.empty:
        st.success("No warning signs detected in this conversation.")
    else:
        severity_filter = st.selectbox("Filter by severity", ["All"] + sorted(alerts_df['severity'].unique().tolist()), label_visibility="collapsed")
        filtered = alerts_df if severity_filter == "All" else alerts_df[alerts_df['severity'] == severity_filter]

        for _, row in filtered.iterrows():
            sev = row['severity']
            badge_class = f"badge-{sev.lower()}"
            
            # Natural phrasing substitution
            reason = row['reason'].replace("Alert: ", "").replace("Warning: ", "")
            if "gang-up attack" in reason.lower():
                reason = "Multiple users appear to be targeting this individual repeatedly."
            elif "escalating toxicity" in reason.lower():
                reason = "A sudden escalation in concerning language was observed."
            elif "high toxicity detected" in reason.lower():
                reason = "Repeated concerning interactions detected."
            elif "overall toxicity" in reason.lower() or "high risk threshold" in reason.lower():
                reason = "The conversation may require attention due to concerning behavior."

            formatted_time = format_timestamp(row['timestamp'])
            
            color_map = {"CRITICAL": "#ef4444", "HIGH": "#f97316", "MEDIUM": "#facc15", "LOW": "#10b981"}
            border_color = color_map.get(sev, "#e2e8f0")
            
            st.markdown(f"""
            <div class="card-bg" style="padding: 16px; border-radius: 8px; margin-bottom: 12px; border-left: 3px solid {border_color};">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                    <div>
                        <span class="badge {badge_class}" style="margin-right: 12px;">{sev}</span>
                        <strong class="text-primary" style="font-size: 15px;">{row['target_user_id']}</strong>
                    </div>
                    <span class="text-secondary" style="font-size: 13px;">{formatted_time}</span>
                </div>
                <div class="text-secondary" style="font-size: 14px; padding-left: 4px;">
                    {reason}
                </div>
            </div>
            """, unsafe_allow_html=True)


# NETWORK GRAPH TAB
with tab_graph:
    st.markdown("<h4 class='text-primary'>Interaction Network</h4>", unsafe_allow_html=True)
    st.markdown("<p class='text-secondary' style='font-size: 14px;'>Visualizing the flow of concerning behavior between individuals.</p>", unsafe_allow_html=True)

    flagged_interactions = repo.get_flagged_interactions()
    if flagged_interactions:
        G = nx.DiGraph()
        for sender, receiver, score in flagged_interactions:
            if G.has_edge(sender, receiver):
                G[sender][receiver]['weight'] += 1
            else:
                G.add_edge(sender, receiver, weight=1)

        risk_lookup = dict(zip(users_df['id'], users_df['risk_score'])) if not users_df.empty else {}

        fig3, ax3 = plt.subplots(figsize=(12, 7))
        fig3.patch.set_facecolor('none')
        ax3.set_facecolor('none')
        pos = nx.spring_layout(G, k=1.8, iterations=50, seed=42)

        node_colors = ['#ef4444' if risk_lookup.get(n, 0) >= 0.7 else '#f97316' if risk_lookup.get(n, 0) >= 0.3 else '#3b82f6' for n in G.nodes()]
        node_sizes = [max(800, G.degree(n) * 400) for n in G.nodes()]
        edge_weights = [G[u][v]['weight'] for u, v in G.edges()]
        max_w = max(edge_weights) if edge_weights else 1
        edge_widths = [1 + (w / max_w) * 4 for w in edge_weights]

        nx.draw_networkx_nodes(G, pos, ax=ax3, node_color=node_colors, node_size=node_sizes, edgecolors='#ffffff', linewidths=2)
        nx.draw_networkx_edges(G, pos, ax=ax3, arrowstyle='->', arrowsize=25, edge_color='#9ca3af',
                               width=edge_widths, alpha=0.6, connectionstyle="arc3,rad=0.1")
        nx.draw_networkx_labels(G, pos, ax=ax3, font_size=10, font_weight='bold', font_color='#ffffff')
        edge_labels = {(u, v): str(d['weight']) for u, v, d in G.edges(data=True)}
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, ax=ax3, font_size=8, font_color='#6b7280', bbox=dict(alpha=0))

        ax3.axis('off')
        plt.tight_layout()
        st.pyplot(fig3)
        plt.close(fig3)

        st.markdown(f"""
        <div style="display: flex; gap: 24px; justify-content: center; margin-top: 16px;">
            <div style="display: flex; align-items: center; gap: 8px;"><span class="risk-badge risk-high"></span><span class="text-secondary" style="font-size: 14px;">High Concern</span></div>
            <div style="display: flex; align-items: center; gap: 8px;"><span class="risk-badge risk-medium"></span><span class="text-secondary" style="font-size: 14px;">Elevated Concern</span></div>
            <div style="display: flex; align-items: center; gap: 8px;"><span class="risk-badge" style="background-color: #3b82f6;"></span><span class="text-secondary" style="font-size: 14px;">Low Concern</span></div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("No concerning interactions to visualize.")


# USERS TAB
with tab_users:
    st.markdown("<h4 class='text-primary'>User Profiles</h4>", unsafe_allow_html=True)
    st.markdown("<p class='text-secondary' style='font-size: 14px;'>Review individual activity and behavior patterns.</p>", unsafe_allow_html=True)

    if users_df.empty:
        st.info("No individuals identified yet.")
    else:
        search = st.text_input("Search for an individual", placeholder="e.g. Charlie", label_visibility="collapsed")
        display = users_df[users_df['username'].str.contains(search, case=False, na=False)] if search else users_df

        for _, row in display.iterrows():
            risk = row['risk_score']
            risk_level = "high" if risk >= 0.7 else "medium" if risk >= 0.3 else "low"
            
            with st.expander(f"{row['username']}", expanded=(risk >= 0.7)):
                uc1, uc2, uc3 = st.columns(3)
                uc1.metric("Concern Score", f"{risk:.2f}")
                uc2.metric("Concerning / Total Messages", f"{row['flagged_messages_count']} / {row['total_messages_sent']}")
                ratio = row['flagged_messages_count'] / row['total_messages_sent'] if row['total_messages_sent'] > 0 else 0
                uc3.metric("Severity Ratio", f"{ratio:.0%}")

                user_flagged = messages_df[(messages_df['sender_id'] == row['id']) & (messages_df['is_flagged'] == 1)]
                if not user_flagged.empty:
                    st.markdown("**Concerning messages sent:**")
                    import json
                    for _, msg in user_flagged.iterrows():
                        target = f" targeting {msg['receiver_id']}" if msg['receiver_id'] else ""
                        
                        # Parse metadata for score breakdown
                        meta_text = ""
                        if 'metadata' in msg and pd.notna(msg['metadata']):
                            try:
                                meta = json.loads(msg['metadata'])
                                method = meta.get('scoring_method', 'unknown')
                                if method == "huggingface":
                                    meta_text = f" [via HF Model: {meta.get('hf_score', 0):.2f}]"
                                elif method == "dictionary":
                                    meta_text = f" [via Dictionary: {meta.get('dict_score', 0):.2f}]"
                                else:
                                    meta_text = f" [via {method}]"
                            except Exception:
                                pass
                                
                        st.markdown(f"- `{msg['timestamp']}`{target}: *\"{msg['content']}\"* (score: **{msg['toxicity_score']:.2f}**){meta_text}")


# VICTIMS TAB
with tab_victims:
    st.markdown("<h4 class='text-primary'>Targeted Individuals</h4>", unsafe_allow_html=True)
    st.markdown("<p class='text-secondary' style='font-size: 14px;'>Individuals who are receiving repeated concerning messages.</p>", unsafe_allow_html=True)

    victims = repo.get_victim_summary()
    if victims:
        for v in victims:
            victim_id, victim_name, times_targeted, distinct_aggressors = v
            risk_level = "high" if distinct_aggressors >= 3 else "medium" if distinct_aggressors >= 2 else "low"

            with st.expander(f"{victim_name}", expanded=(distinct_aggressors >= 2)):
                vc1, vc2 = st.columns(2)
                vc1.metric("Messages received", times_targeted)
                vc2.metric("Distinct senders", distinct_aggressors)

                if distinct_aggressors >= 2:
                    st.warning(f"Multiple individuals are directing concerning messages at {victim_name}.")

                # Show evidence
                targeted_msgs = repo.get_messages_targeting_user(victim_id)
                if targeted_msgs:
                    st.markdown("**Messages received:**")
                    import json
                    for tm in targeted_msgs:
                        meta_text = ""
                        if len(tm) > 4 and tm[4]:
                            try:
                                meta = json.loads(tm[4])
                                method = meta.get('scoring_method', 'unknown')
                                if method == "huggingface":
                                    meta_text = f" [via HF Model: {meta.get('hf_score', 0):.2f}]"
                                elif method == "dictionary":
                                    meta_text = f" [via Dictionary: {meta.get('dict_score', 0):.2f}]"
                                else:
                                    meta_text = f" [via {method}]"
                            except Exception:
                                pass
                        st.markdown(f"- `{tm[0][:19]}` **{tm[1]}**: *\"{tm[2]}\"* (score: {tm[3]:.2f}){meta_text}")
    else:
        st.success("No targeted individuals identified.")


# REPORTS TAB
with tab_reports:
    st.markdown("<h4 class='text-primary'>Export Summaries</h4>", unsafe_allow_html=True)
    st.markdown(
        "<p class='text-secondary' style='font-size: 14px;'>Download actionable summaries and data exports for further review.</p>",
        unsafe_allow_html=True
    )

    col_gen, col_csv = st.columns(2)

    with col_gen:
        st.markdown(f"""
        <div class="metric-card card-bg" style="margin-bottom: 16px;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
                {get_svg_icon('document', size=24, color='#3b82f6')}
                <strong class="text-primary" style="font-size: 16px;">Full Summary Report</strong>
            </div>
            <p class="text-secondary" style="font-size: 14px; margin: 0 0 16px 0;">A complete overview of the conversation, key warnings, and individuals involved.</p>
        </div>
        """, unsafe_allow_html=True)
        
        if 'pdf_ready' not in st.session_state:
            if st.button("Prepare Report", use_container_width=True, type="primary"):
                with st.spinner("Preparing document..."):
                    report_gen = ReportGenerator(repo)
                    st.session_state['pdf_ready'] = report_gen.generate_pdf_report()
                st.rerun()
        else:
            st.download_button(
                label="Download PDF Report",
                data=bytes(st.session_state['pdf_ready']),
                file_name=f"safenet_summary_{datetime.now():%Y%m%d_%H%M}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    with col_csv:
        st.markdown(f"""
        <div class="metric-card card-bg" style="margin-bottom: 16px;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
                {get_svg_icon('database', size=24, color='#10b981')}
                <strong class="text-primary" style="font-size: 16px;">Data Export</strong>
            </div>
            <p class="text-secondary" style="font-size: 14px; margin: 0 0 16px 0;">Raw spreadsheet format containing all logged warning signs.</p>
        </div>
        """, unsafe_allow_html=True)
        csv_bytes = repo.get_alerts_csv_bytes()
        st.download_button(
            label="Download Spreadsheet",
            data=csv_bytes,
            file_name=f"safenet_data_{datetime.now():%Y%m%d_%H%M}.csv",
            mime="text/csv",
            use_container_width=True,
        )


# RAW DATA TAB
with tab_data:
    st.markdown("<h4 class='text-primary'>Raw Data Viewer</h4>", unsafe_allow_html=True)
    dt1, dt2, dt3 = st.tabs(["Messages", "Users", "Alerts"])
    with dt1:
        st.dataframe(messages_df, use_container_width=True, height=400)
    with dt2:
        st.dataframe(users_df, use_container_width=True, height=400)
    with dt3:
        st.dataframe(alerts_df, use_container_width=True, height=400)


with tab_extension_audit:
    render_extension_audit_tab(repo)
