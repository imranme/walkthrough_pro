"""
ui.py
-----
Streamlit test interface for the T-TESS AI Coaching Observer.

Run with:
    streamlit run app/frontend/ui.py

Mirrors the Figma observation form exactly:
  Domain 2: Classroom Environment
    - Creating an Environment of Respect
    - Establishing a Culture for Learning
    - Managing Classroom Procedures
    - Managing Student Behavior

  Domain 3: Instruction
    - Communicating with Students
    - Using Questioning and Discussion
    - Engaging Students in Learning
    - Using Assessment in Instruction

  Observation Notes (free text)
  Submit Observation → AI Coaching Results
"""

from __future__ import annotations

import logging
import json
import sys
from datetime import date, time
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Path bootstrap — walk up from this file until we find `app/common/`
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve()
_APP_DIR = _HERE.parent        # app/frontend/ → walk up to app/
for _ in range(6):
    if (_APP_DIR / "common").is_dir():
        break
    _APP_DIR = _APP_DIR.parent

if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from common.custom_exception import (
    ConfigurationError,
    InvalidObservationDataError,
    OpenAIClientError,
    OpenAIRateLimitError,
    OpenAITimeoutError,
    RubricParsingError,
    TTESSBaseException,
)
from components.generator import (
    DOMAIN_DIMENSION_MAP,
    CoachingResult,
    ObservationData,
    generate_coaching_result,
)

logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="T-TESS AI Coaching Observer",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# CSS — dark header, white cards, score bars, badges
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background: #f0f2f6; }

/* ── Header bar ─────────────────────────────────── */
.ttess-header {
    background: #1a2744;
    color: #fff !important;
    padding: 16px 24px 12px;
    border-radius: 12px;
    margin-bottom: 20px;
}
.ttess-header h2 { margin: 0; font-size: 1.2rem; font-weight: 700; color: #fff !important; }
.ttess-header p  { margin: 2px 0 0; font-size: 0.8rem; opacity: 0.65; color: #fff !important; }

/* ── Card ───────────────────────────────────────── */
.card {
    background: #fff;
    border-radius: 14px;
    padding: 18px 22px 14px;
    margin-bottom: 18px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.card-title {
    font-size: 1rem;
    font-weight: 700;
    color: #1a2744;
    margin-bottom: 14px;
    border-bottom: 2px solid #e8ecf4;
    padding-bottom: 8px;
}

/* ── Score bar (results page) ───────────────────── */
.score-row { display:flex; align-items:center; gap:10px; margin-bottom:12px; }
.score-label { flex:0 0 240px; font-size:0.82rem; color:#444; }
.score-val   { flex:0 0 32px; font-size:0.82rem; font-weight:700; color:#1a2744; }
.score-bar-bg { flex:1; height:7px; background:#e8ecf4; border-radius:4px; overflow:hidden; }
.score-bar-fill { height:100%; border-radius:4px; background:linear-gradient(90deg,#3b82f6,#6366f1); }

/* ── Overall score ──────────────────────────────── */
.overall-score { font-size:3rem; font-weight:800; color:#1a2744; }
.overall-denom { font-size:1.3rem; color:#888; margin-left:2px; }

/* ── Rating badge ───────────────────────────────── */
.badge { display:inline-block; padding:3px 10px; border-radius:20px; font-size:0.75rem; font-weight:600; }
.badge-Distinguished      { background:#d1fae5; color:#065f46; }
.badge-Accomplished       { background:#dbeafe; color:#1e40af; }
.badge-Proficient         { background:#e0e7ff; color:#3730a3; }
.badge-Developing         { background:#fef3c7; color:#92400e; }
.badge-ImprovementNeeded  { background:#fee2e2; color:#991b1b; }

/* ── Dimension body ─────────────────────────────── */
.dim-body { padding:10px 0 4px; font-size:0.85rem; color:#444; line-height:1.65; }
.dim-section-label { font-weight:700; color:#1a2744; margin-top:8px; display:block; }

/* ── Submit button ──────────────────────────────── */
div[data-testid="stButton"] > button {
    background:#1a2744; color:#fff; border:none;
    border-radius:10px; font-weight:700; font-size:0.95rem;
    padding:12px 0; width:100%; transition:opacity .2s;
}
div[data-testid="stButton"] > button:hover { opacity:.85; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init_state() -> None:
    for k, v in [("screen", "form"), ("result", None), ("obs_data", None), ("generating", False)]:
        if k not in st.session_state:
            st.session_state[k] = v


def _badge(rating: str) -> str:
    css = rating.replace(" ", "")
    return f'<span class="badge badge-{css}">{rating}</span>'


def _score_bar(label: str, score: float, max_score: float = 4.0) -> str:
    pct = (score / max_score) * 100
    return (
        f'<div class="score-row">'
        f'  <span class="score-label">{label}</span>'
        f'  <span class="score-val">{score}</span>'
        f'  <div class="score-bar-bg">'
        f'    <div class="score-bar-fill" style="width:{pct}%"></div>'
        f'  </div>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Screen 1 — Observation Form  (matches Figma exactly)
# ---------------------------------------------------------------------------

def _render_form() -> None:
    st.markdown(
        '<div class="ttess-header">'
        '<h2>🏫 Observation Form</h2>'
        '<p>Complete the form to begin</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    with st.form("observation_form"):

        # ── Teacher / class info ───────────────────────────────────────────
        st.markdown('<div class="card"><div class="card-title">Basic Information</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            teacher_name = st.text_input("Select Teacher", placeholder="e.g. Sarah Thompson")
            subject      = st.text_input("Subject", placeholder="e.g. World History")
        with col2:
            grade_level  = st.text_input("Grade Level", placeholder="e.g. Grade 10")
            obs_date     = st.date_input("Date", value=date.today())
        obs_time = st.time_input("Time", value=time(9, 0))
        st.markdown("</div>", unsafe_allow_html=True)

        # ── Domain 2: Classroom Environment ───────────────────────────────
        st.markdown(
            '<div class="card">'
            '<div class="card-title">Domain 2: Classroom Environment</div>',
            unsafe_allow_html=True,
        )
        d2_creating   = st.slider("Creating an Environment of Respect",    1.0, 4.0, 3.0, 0.1)
        d2_culture    = st.slider("Establishing a Culture for Learning",    1.0, 4.0, 2.8, 0.1)
        d2_procedures = st.slider("Managing Classroom Procedures",          1.0, 4.0, 3.3, 0.1)
        d2_behavior   = st.slider("Managing Student Behavior",              1.0, 4.0, 3.2, 0.1)
        d2_avg = round((d2_creating + d2_culture + d2_procedures + d2_behavior) / 4, 1)
        st.caption(f"Domain 2 average: **{d2_avg} / 4**")
        st.markdown("</div>", unsafe_allow_html=True)

        # ── Domain 3: Instruction ──────────────────────────────────────────
        st.markdown(
            '<div class="card">'
            '<div class="card-title">Domain 3: Instruction</div>',
            unsafe_allow_html=True,
        )
        d3_communicating = st.slider("Communicating with Students",         1.0, 4.0, 3.0, 0.1)
        d3_questioning   = st.slider("Using Questioning and Discussion",    1.0, 4.0, 2.8, 0.1)
        d3_engaging      = st.slider("Engaging Students in Learning",       1.0, 4.0, 3.3, 0.1)
        d3_assessment    = st.slider("Using Assessment in Instruction",     1.0, 4.0, 3.2, 0.1)
        d3_avg = round((d3_communicating + d3_questioning + d3_engaging + d3_assessment) / 4, 1)
        st.caption(f"Domain 3 average: **{d3_avg} / 4**")
        st.markdown("</div>", unsafe_allow_html=True)

        # ── Observation Notes ──────────────────────────────────────────────
        st.markdown(
            '<div class="card">'
            '<div class="card-title">💬 Observation Notes</div>',
            unsafe_allow_html=True,
        )
        obs_notes = st.text_area(
            "Observation Notes",
            placeholder=(
                "CO: Content objective — e.g. Students will analyze...\n"
                "LO: Language objective — e.g. Students will use vocabulary...\n\n"
                "Describe what you observed during the lesson..."
            ),
            height=220,
            label_visibility="collapsed",
        )
        st.markdown("</div>", unsafe_allow_html=True)

        submitted = st.form_submit_button("Submit Observation", use_container_width=True)

    # ── Handle submission ──────────────────────────────────────────────────
    if submitted:
        # Clear any previous result immediately so old data is never shown
        st.session_state["result"] = None
        st.session_state["screen"] = "form"
        obs = ObservationData(
            teacher_name=teacher_name,
            subject=subject,
            grade_level=grade_level,
            date=str(obs_date),
            time=str(obs_time),
            observation_notes=obs_notes,
            # Domain 2
            d2_creating_environment=d2_creating,
            d2_culture_for_learning=d2_culture,
            d2_classroom_procedures=d2_procedures,
            d2_student_behavior=d2_behavior,
            # Domain 3
            d3_communicating_students=d3_communicating,
            d3_questioning_discussion=d3_questioning,
            d3_engaging_learning=d3_engaging,
            d3_assessment_instruction=d3_assessment,
        )

        st.session_state["generating"] = True
        with st.spinner("Generating AI coaching results…"):
            try:
                result = generate_coaching_result(obs)
                st.session_state["generating"] = False
                st.session_state["result"]   = result
                st.session_state["obs_data"] = obs
                st.session_state["screen"]   = "results"
                st.rerun()

            except ConfigurationError as exc:
                st.session_state["generating"] = False
                st.error(f"⚙️ Configuration error: {exc}")
            except InvalidObservationDataError as exc:
                st.warning(f"⚠️ {exc.message}"
                           + (f" (field: {exc.field})" if exc.field else ""))
            except OpenAIRateLimitError:
                st.error("🚦 OpenAI rate limit hit. Please wait a moment and try again.")
            except OpenAITimeoutError:
                st.error("⏱️ The request timed out. Please try again.")
            except OpenAIClientError as exc:
                st.error(f"🤖 OpenAI error: {exc}")
            except RubricParsingError as exc:
                st.error(f"📋 Could not parse AI response: {exc}")
            except TTESSBaseException as exc:
                st.error(f"❌ Unexpected error: {exc}")


# ---------------------------------------------------------------------------
# Screen 2 — AI Coaching Results
# ---------------------------------------------------------------------------

def _render_results() -> None:
    result: CoachingResult  = st.session_state["result"]
    obs:    ObservationData = st.session_state["obs_data"]

    st.markdown(
        f'<div class="ttess-header">'
        f'<h2>🎯 AI Coaching Results</h2>'
        f'<p>{result.teacher_name} · {result.date}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    col_left, col_right = st.columns([1, 1], gap="large")

    # ── Left column ────────────────────────────────────────────────────────
    with col_left:

        # Overall score
        st.markdown(
            f'<div class="card">'
            f'<div class="card-title">Overall Performance Score</div>'
            f'<span class="overall-score">{result.overall_score}</span>'
            f'<span class="overall-denom"> / 4</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Domain scores
        domain_html = '<div class="card"><div class="card-title">Domain Scores</div>'
        for domain, score in result.domain_scores.items():
            domain_html += _score_bar(domain, score)
        domain_html += "</div>"
        st.markdown(domain_html, unsafe_allow_html=True)

        # Raw notes summary
        st.markdown(
            f'<div class="card">'
            f'<div class="card-title">🗒️ Raw Notes</div>'
            f'<p style="font-size:0.85rem;color:#444;line-height:1.75">'
            f'{result.raw_notes_summary}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Right column — AI Coaching Output ─────────────────────────────────
    with col_right:
        st.markdown(
            '<div class="card"><div class="card-title">🤖 AI Coaching Output</div>',
            unsafe_allow_html=True,
        )

        # Group by domain for cleaner display
        domain2_dims = [d for d in result.dimensions if d.dimension_id.startswith("2.")]
        domain3_dims = [d for d in result.dimensions if d.dimension_id.startswith("3.")]

        for domain_label, dims in [
            ("Domain 2 — Classroom Environment", domain2_dims),
            ("Domain 3 — Instruction",           domain3_dims),
        ]:
            st.markdown(
                f'<p style="font-weight:700;color:#1a2744;margin:12px 0 6px;'
                f'font-size:0.88rem;border-top:1px solid #e8ecf4;padding-top:10px">'
                f'{domain_label}</p>',
                unsafe_allow_html=True,
            )
            for dim in dims:
                with st.expander(
                    f"{dim.dimension_id}  {dim.dimension_name}",
                    expanded=False,
                ):
                    # Observer score vs AI rating side by side
                    c1, c2 = st.columns(2)
                    with c1:
                        st.caption("Observer Score")
                        st.markdown(f"**{dim.observer_score} / 4**")
                    with c2:
                        st.caption("AI Rating")
                        st.markdown(_badge(dim.rating), unsafe_allow_html=True)

                    st.markdown(
                        f'<div class="dim-body">'
                        f'<span class="dim-section-label">📌 Coaching Feedback</span>'
                        f'<p>{dim.coaching_feedback}</p>'
                        f'<span class="dim-section-label">🚀 Growth Suggestion</span>'
                        f'<p>{dim.growth_suggestion}</p>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

        st.markdown("</div>", unsafe_allow_html=True)

    # ── JSON Export + Back button ────────────────────────────────────
    st.divider()
    export_data = {
        "teacher_name": result.teacher_name,
        "date": result.date,
        "overall_score": result.overall_score,
        "domain_scores": result.domain_scores,
        "raw_notes_summary": result.raw_notes_summary,
        "dimensions": [
            {
                "dimension_id": d.dimension_id,
                "dimension_name": d.dimension_name,
                "observer_score": d.observer_score,
                "rating": d.rating,
                "rating_numeric": d.rating_numeric,
                "coaching_feedback": d.coaching_feedback,
                "growth_suggestion": d.growth_suggestion,
            }
            for d in result.dimensions
        ],
    }
    col_dl, col_back = st.columns([1, 4])
    with col_dl:
        st.download_button(
            label="⬇️ Download JSON",
            data=json.dumps(export_data, indent=2, ensure_ascii=False),
            file_name=f"coaching_{result.teacher_name.replace(' ', '_')}_{result.date}.json",
            mime="application/json",
        )
    with col_back:
        if st.button("← Back to Home", use_container_width=False):
            st.session_state["screen"] = "form"
            st.session_state["result"] = None
            st.rerun()


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def main() -> None:
    _init_state()
    # Only show results if we actually have a result and are not mid-generation
    if st.session_state["screen"] == "results" and st.session_state["result"] is not None and not st.session_state["generating"]:
        _render_results()
    else:
        _render_form()


if __name__ == "__main__":
    main()