"""
generator.py
------------
AI Coaching Result Generator for the T-TESS Observation Tool.

Responsibilities
----------------
1. Validate raw observation form data.
2. Build a structured prompt aligned with the T-TESS rubric dimensions.
3. Call the Anthropic Claude API and parse the JSON response.
4. AI autonomously assigns ratings based ONLY on observation evidence.
5. Return a strongly-typed CoachingResult object.
6. Support rewriting a report after manual rating overrides.

T-TESS Dimensions covered
--------------------------
Domain 2 – Instruction
    2.1  Achieving Expectations
    2.2  Content Knowledge & Expertise
    2.3  Communication
    2.4  Differentiation
    2.5  Monitor & Adjust

Domain 3 – Learning Environment
    3.1  Classroom Environment, Routines & Procedures
    3.2  Managing Student Behavior
    3.3  Classroom Culture

Rating Scale
------------
Distinguished | Accomplished | Proficient | Development |
Needs Improvement | Not Enough Evidence
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
# Project layout:
#   app/
#     common/
#     components/
#         generator.py   <- THIS file
#     config/
#     frontend/
#         ui.py
#
# Walk upward from generator.py until we reach the folder that contains
# `common/` (i.e. `app/`) and add it to sys.path so that sibling packages
# `common` and `config` are importable.
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve()
_APP_DIR = _HERE.parent          # start at app/components/
for _ in range(6):               # safety guard
    if (_APP_DIR / "common").is_dir():
        break
    _APP_DIR = _APP_DIR.parent

if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — match exactly what the UI shows
# ---------------------------------------------------------------------------

DIMENSIONS: dict[str, str] = {
    "2.1": "Achieving Expectations",
    "2.2": "Content Knowledge & Expertise",
    "2.3": "Communication",
    "2.4": "Differentiation",
    "2.5": "Monitor & Adjust",
    "3.1": "Classroom Environment, Routines & Procedures",
    "3.2": "Managing Student Behavior",
    "3.3": "Classroom Culture",
}

DOMAIN_DIMENSION_MAP: dict[str, list[str]] = {
    "Domain 2 - Instruction":            ["2.1", "2.2", "2.3", "2.4", "2.5"],
    "Domain 3 - Learning Environment":   ["3.1", "3.2", "3.3"],
}

VALID_RATINGS = [
    "Distinguished",
    "Accomplished",
    "Proficient",
    "Development",
    "Needs Improvement",
    "Not Enough Evidence",
]

RATING_NUMERIC: dict[str, float] = {
    "Distinguished":      4.0,
    "Accomplished":       3.5,
    "Proficient":         3.0,
    "Development":        2.0,
    "Needs Improvement":  1.0,
    "Not Enough Evidence": 0.0,
}

SUBJECTS = [
    "English Language Arts",
    "Mathematics",
    "Science",
    "Social Studies",
    "Health Education",
    "Physical Education",
    "Languages Other Than English",
    "Fine Arts",
    "Economics",
    "Technology Applications",
    "Spanish Language Arts & EST",
    "Reading",
    "Writing",
    "Career & Technical Education",
    "Speech",
]

GRADE_LEVELS = [str(i) for i in range(13)]  # 0–12


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ObservationData:
    """Input payload representing a completed observation form."""
    teacher_name:       str
    subject:            str
    grade_level:        str
    date:               str
    time:               str
    observation_notes:  str
    selected_domains:   list[str] = field(default_factory=list)


@dataclass
class DimensionResult:
    """AI-generated coaching output for a single T-TESS dimension."""
    dimension_id:       str
    dimension_name:     str
    ai_rating:          str   # AI-assigned rating (may be overridden by user)
    user_rating:        str   # Current rating (starts == ai_rating, user can change)
    rating_numeric:     float
    evidence:           str   # Evidence paragraph
    why_this_rating:    str   # Explanation of why this rating was chosen
    glow:               str   # Strength noted
    grow:               str   # Area for growth
    action_step:        str   # Next-class action step
    look_fors:          list[str]  # Bullet look-fors for next walkthrough


@dataclass
class CoachingResult:
    """Full AI coaching output for one observation."""
    teacher_name:       str
    date:               str
    raw_notes_summary:  str

    dimensions: list[DimensionResult] = field(default_factory=list)
    domain_scores:  dict[str, float] = field(default_factory=dict)
    overall_score:  float = 0.0

    def compute_scores(self) -> None:
        """Calculate domain averages and overall score, ignoring NEE dimensions."""
        domain_sums: dict[str, list[float]] = {d: [] for d in DOMAIN_DIMENSION_MAP}
        for dim in self.dimensions:
            if dim.user_rating == "Not Enough Evidence":
                continue
            for domain, dim_ids in DOMAIN_DIMENSION_MAP.items():
                if dim.dimension_id in dim_ids:
                    domain_sums[domain].append(RATING_NUMERIC[dim.user_rating])

        self.domain_scores = {
            domain: round(sum(scores) / len(scores), 2) if scores else 0.0
            for domain, scores in domain_sums.items()
        }
        all_scores = [s for scores in domain_sums.values() for s in scores]
        self.overall_score = (
            round(sum(all_scores) / len(all_scores), 2) if all_scores else 0.0
        )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """
You are an expert instructional coach certified in the Texas Teacher Evaluation and Support System (T-TESS).

Your task is to generate structured coaching feedback for each requested T-TESS dimension using ONLY
the observation notes provided. You must NOT fabricate, assume, or infer anything not explicitly
present in the notes.

═══════════════════════════════════════════════════════════════
CRITICAL RATING RULES — READ CAREFULLY
═══════════════════════════════════════════════════════════════
You have SIX possible ratings:
  1. Distinguished
  2. Accomplished
  3. Proficient
  4. Development
  5. Needs Improvement
  6. Not Enough Evidence

WHEN TO USE "Not Enough Evidence":
  • The observation notes contain NO observable evidence for this dimension.
  • You MUST use "Not Enough Evidence" if you cannot cite a specific, concrete moment
    from the notes. Do NOT guess or generate generic feedback for unseen events.
  • When rating is "Not Enough Evidence", set evidence, glow, grow, action_step to
    "Not Enough Evidence" and look_fors to 3 specific things to watch for next time.

WHEN TO USE OTHER RATINGS:
  • Only when you can cite SPECIFIC, EXPLICIT evidence from the observation notes.
  • Choose the rating that best matches the rubric descriptor below for what was observed.
  • The rating must reflect what actually happened, not what the teacher might normally do.

═══════════════════════════════════════════════════════════════
RUBRIC DESCRIPTORS
═══════════════════════════════════════════════════════════════

━━ DIMENSION 2.1 — Achieving Expectations ━━
Goal: The teacher supports all learners in pursuit of high levels of academic and social-emotional success.
  Distinguished:      Persists until ALL students demonstrate mastery. Provides opportunities for students
                      to self-monitor and self-correct. Systematically enables students to set goals.
  Accomplished:       Persists until MOST students show mastery. Anticipates student mistakes.
                      Establishes systems for student initiative and self-monitoring.
  Proficient:         Sets academic expectations challenging ALL students. Persists until most show mastery.
                      Addresses mistakes and follows through. Provides initiative opportunities.
  Development:        Sets expectations challenging MOST students. Persists until SOME show mastery.
                      Sometimes addresses mistakes. Sometimes provides initiative opportunities.
  Needs Improvement:  Sets expectations challenging FEW students. Allows mistakes to go unaddressed.
                      Rarely provides initiative opportunities.

━━ DIMENSION 2.2 — Content Knowledge & Expertise ━━
Goal: The teacher uses content and pedagogical expertise to design and execute lessons aligned with standards.
  Distinguished:      Displays extensive content knowledge. Integrates objectives with disciplines and
                      real-world experience. Consistently anticipates misunderstandings. Provides varied
                      thinking types (analytical, practical, creative, research-based).
  Accomplished:       Conveys depth of knowledge. Integrates objectives with other disciplines and
                      real-world experiences. Anticipates misunderstandings proactively.
  Proficient:         Conveys accurate content knowledge in multiple contexts. Integrates with other
                      disciplines. Anticipates possible misunderstandings.
  Development:        Conveys accurate content knowledge. Sometimes integrates disciplines.
                      Sometimes anticipates misunderstandings.
  Needs Improvement:  Conveys inaccurate content. Rarely integrates disciplines. Does not anticipate
                      misunderstandings.

━━ DIMENSION 2.3 — Communication ━━
Goal: The teacher clearly communicates to support persistence, deeper learning, and effective effort.
  Distinguished:      ALL students communicate safely using varied tools. Uses misunderstandings
                      strategically. Asks creative/evaluative questions. Skillfully balances wait time.
  Accomplished:       All students communicate effectively using visual tools and technology.
                      Anticipates misunderstandings. Asks analysis-level questions provoking discussion.
  Proficient:         MOST students communicate with teacher and peers. Recognizes misunderstandings.
                      Asks remember/understand/apply questions. Uses probing questions.
  Development:        SOME opportunity for dialogue. Recognizes misunderstandings but limited response.
                      Generally clear with minor errors.
  Needs Improvement:  LITTLE opportunity for dialogue. Unresponsive to misunderstandings.
                      Inaccurate communication.

━━ DIMENSION 2.4 — Differentiation ━━
Goal: The teacher differentiates instruction, aligning methods to diverse student needs.
  Distinguished:      WIDE VARIETY of strategies for ALL students' individual needs. Consistently
                      monitors participation. Always provides differentiated methods and content.
  Accomplished:       Adapts lessons for ALL students. Regularly monitors. Proactively minimizes
                      confusion by addressing learning and social/emotional needs.
  Proficient:         Adapts lessons for ALL students. Provides differentiated methods. Recognizes
                      confusion/disengagement and responds.
  Development:        Adapts for SOME students. Sometimes monitors. Sometimes recognizes
                      confusion/disengagement.
  Needs Improvement:  One-size-fits-all lessons. Rarely monitors. Does not recognize confusion.

━━ DIMENSION 2.5 — Monitor & Adjust ━━
Goal: The teacher collects and uses student progress data and makes needed lesson adjustments.
  Distinguished:      Systematically gathers input to adjust instruction for ALL students.
                      Uses discreet and explicit checks through questioning and academic feedback.
  Accomplished:       Utilizes student input to adjust instruction, activities, AND pacing.
                      Continually checks for understanding through purposeful questioning.
  Proficient:         Adjusts instruction based on student data. Uses formal and informal assessments.
                      Adjusts for most students.
  Development:        Makes minimal adjustments. Uses limited checks for understanding.
                      Some adjustments are reactive rather than proactive.
  Needs Improvement:  Rarely adjusts instruction. Does not check for understanding.
                      Continues lesson regardless of student mastery.

━━ DIMENSION 3.1 — Classroom Environment, Routines & Procedures ━━
Goal: The teacher organizes a safe, accessible, and efficient classroom.
  Distinguished:      Routines rely on STUDENT leadership. Students take primary responsibility
                      for managing groups, supplies. Classroom designed to inspire beyond objectives.
  Accomplished:       Effective routines implemented effortlessly. Students take SOME responsibility.
                      Classroom is inviting and organized to support objectives.
  Proficient:         All procedures and transitions are clear and efficient. Students manage supplies
                      with very limited teacher direction. Classroom is safe and organized.
  Development:        MOST procedures clear but others are unclear. Students depend on teacher.
                      Classroom is safe but sometimes disorganized.
  Needs Improvement:  FEW procedures guide behavior. Transitions are confused. Classroom is unsafe.

━━ DIMENSION 3.2 — Managing Student Behavior ━━
Goal: The teacher establishes, communicates, and maintains clear expectations for student behavior.
  Distinguished:      Monitors behavior SUBTLY. Intercepts misbehavior fluidly. Students AND teacher
                      create and maintain standards together.
  Accomplished:       Encourages and monitors behavior subtly. Responds to misbehavior SWIFTLY.
                      Most students know and respect behavior standards.
  Proficient:         Implements behavior system PROFICIENTLY. Most students meet expected standards.
  Development:        INCONSISTENTLY implements behavior system. Some failure interrupts learning.
  Needs Improvement:  RARELY enforces standards. Student behavior impedes learning.

━━ DIMENSION 3.3 — Classroom Culture ━━
Goal: The teacher leads a mutually respectful and collaborative class of actively engaged learners.
  Distinguished:      ALL students engaged with meaningful learning. Students collaborate positively
                      and encourage each other. Creates positive rapport.
  Accomplished:       ALL students engaged with meaningful learning. Students collaborate positively
                      with each other and the teacher.
  Proficient:         ALL students engaged in relevant, meaningful learning. Students work respectfully.
  Development:        MOST students are engaged. Students are SOMETIMES disrespectful.
  Needs Improvement:  FEW students are engaged. Students are disrespectful of each other AND teacher.

═══════════════════════════════════════════════════════════════
DEPTH & LENGTH REQUIREMENTS — READ CAREFULLY
═══════════════════════════════════════════════════════════════

For EVERY dimension with sufficient evidence, you MUST write:

EVIDENCE (minimum 4–6 sentences):
  • Open with the specific instructional moment you observed (quote or closely paraphrase from the notes).
  • Describe WHAT the teacher did and HOW students responded with observable, behavioral detail.
  • Reference at least 2 distinct episodes or data points from the notes.
  • Connect the observed behavior to the dimension's stated goal.
  • Note any patterns (consistent vs. isolated) and how they shaped the learning environment.
  • If partial evidence exists, acknowledge what was present and what was absent.

WHY THIS RATING (minimum 3–4 sentences):
  • State the specific rubric descriptor that best matches what was observed.
  • Explain WHY a higher rating was NOT awarded — what specific rubric criteria were missing or only partially met.
  • Explain WHY a lower rating was NOT awarded — what positive evidence elevated the rating above the floor.
  • Ground every claim in language drawn directly from the rubric descriptors above.

GLOW (minimum 3–4 sentences):
  • Name a concrete, specific strength with an example from the notes.
  • Explain the IMPACT of that strength on student learning or engagement.
  • Connect it to best practice or the rubric's highest descriptors so the teacher understands its value.

GROW (minimum 3–4 sentences):
  • Identify the most critical, specific gap between current practice and the next rating level.
  • Describe what that gap looks like in the classroom using observable language.
  • Explain the potential instructional impact if this gap is closed.

ACTION STEP (minimum 3–4 sentences):
  • Give ONE concrete, implementable strategy for the very next class period.
  • Describe HOW to implement it step-by-step (not just what to do, but how).
  • Explain the expected student outcome so the teacher knows what success looks like.
  • Optionally name a research-backed technique (think-pair-share, cold-call, exit ticket, etc.).

LOOK-FORS (exactly 4 items, each 1–2 sentences):
  • Each look-for describes a specific, OBSERVABLE teacher OR student behavior to watch for next walkthrough.
  • Write them as complete sentences: "Students will…" or "The teacher will…" — not fragments.
  • Each must be distinct and measurable, tied directly to the gap or growth area identified.

═══════════════════════════════════════════════════════════════
OUTPUT FORMAT — valid JSON only, no markdown fences, no preamble
═══════════════════════════════════════════════════════════════
{
  "raw_notes_summary": "4-5 sentence summary of the observed lesson capturing the content objective, instructional strategies used, student engagement patterns, and the overall arc of the lesson — only from what was explicitly observed in the notes.",
  "dimensions": [
    {
      "dimension_id": "2.1",
      "ai_rating": "Proficient",
      "evidence": "Multi-sentence evidence paragraph (minimum 4–6 sentences) citing specific, concrete moments from the observation notes with behavioral detail and student response.",
      "why_this_rating": "Multi-sentence explanation (minimum 3–4 sentences) anchored in rubric language, explaining why this rating and not the one above or below.",
      "glow": "Multi-sentence strength statement (minimum 3–4 sentences) with specific example, impact on learning, and connection to best practice.",
      "grow": "Multi-sentence growth area (minimum 3–4 sentences) naming the gap, what it looks like, and what closing it would achieve.",
      "action_step": "Multi-sentence action step (minimum 3–4 sentences) giving a concrete, step-by-step strategy for the next class with expected student outcome.",
      "look_fors": [
        "Complete sentence describing observable teacher or student behavior 1 (1–2 sentences).",
        "Complete sentence describing observable teacher or student behavior 2 (1–2 sentences).",
        "Complete sentence describing observable teacher or student behavior 3 (1–2 sentences).",
        "Complete sentence describing observable teacher or student behavior 4 (1–2 sentences)."
      ]
    }
  ]
}

REMINDER: If there is not enough evidence for a dimension, use:
  "ai_rating": "Not Enough Evidence",
  "evidence": "Not Enough Evidence",
  "why_this_rating": "Not Enough Evidence",
  "glow": "Not Enough Evidence",
  "grow": "Not Enough Evidence",
  "action_step": "Not Enough Evidence",
  "look_fors": [
    "Watch for: <specific observable behavior to look for next walkthrough — 1 sentence>.",
    "Watch for: <specific observable behavior to look for next walkthrough — 1 sentence>.",
    "Watch for: <specific observable behavior to look for next walkthrough — 1 sentence>.",
    "Watch for: <specific observable behavior to look for next walkthrough — 1 sentence>."
  ]
""".strip()


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------
def _build_user_prompt(data: ObservationData, manual_ratings: dict[str, str] | None = None) -> str:
    lines = [
        f"Teacher : {data.teacher_name}",
        f"Subject : {data.subject}",
        f"Grade   : {data.grade_level}",
        f"Date    : {data.date}",
        f"Time    : {data.time}",
        "",
    ]

    if manual_ratings:
        lines += [
            "=== REWRITE REQUEST ===",
            "The observer has manually changed some ratings. Rewrite the coaching feedback",
            "(evidence, glow, grow, action_step, look_fors) to be consistent with the new ratings below.",
            "Do NOT change any rating that is not listed here. Keep unchanged ratings as-is.",
            "",
            "Manual rating overrides:",
        ]
        for dim_id, rating in manual_ratings.items():
            lines.append(f"  {dim_id} {DIMENSIONS.get(dim_id, '')} → {rating}")
        lines += [
            "",
            "IMPORTANT: When rewriting for a manually set rating, ensure the feedback",
            "is grounded in evidence from the observation notes AND consistent with the",
            "rubric descriptor for the new rating level.",
            "",
            "=== CRITICAL ===",
            "You MUST return ALL dimensions in the JSON response, not just the overridden ones.",
            "Every dimension from the original result must appear in your output.",
            "",
        ]

    dims_to_eval = []
    for domain, dim_ids in DOMAIN_DIMENSION_MAP.items():
        if domain in data.selected_domains:
            dims_to_eval.extend(dim_ids)

    if not dims_to_eval:
        dims_to_eval = list(DIMENSIONS.keys())

    dim_lines = [f"  - {dim_id}: {DIMENSIONS.get(dim_id, '')}" for dim_id in dims_to_eval]

    lines += [
        "=== CRITICAL INSTRUCTION ===",
        f"You MUST evaluate ALL {len(dims_to_eval)} dimensions listed below.",
        f"Your JSON response MUST contain exactly {len(dims_to_eval)} objects in the 'dimensions' array.",
        "Do NOT stop after the first dimension. Do NOT skip any dimension.",
        "Every single dimension below requires its own complete JSON entry.",
        "",
        "=== Dimensions to evaluate (ALL REQUIRED) ===",
    ]
    lines += dim_lines
    lines += [
        "",
        "=== Observation Notes ===",
        data.observation_notes.strip(),
    ]
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def _parse_response(raw_json: str, data: ObservationData) -> CoachingResult:
    """Parse the JSON string from the model into a CoachingResult."""
    try:
        payload: dict[str, Any] = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"AI response is not valid JSON. Raw (first 300): {raw_json[:300]}"
        ) from exc

    summary = payload.get("raw_notes_summary", "").strip()
    result = CoachingResult(
        teacher_name=data.teacher_name,
        date=data.date,
        raw_notes_summary=summary,
    )

    raw_dims: list[dict] = payload.get("dimensions", [])
    for item in raw_dims:
        dim_id = str(item.get("dimension_id", "")).strip()
        ai_rating = str(item.get("ai_rating", "Not Enough Evidence")).strip()

        if dim_id not in DIMENSIONS:
            logger.warning("Unrecognised dimension_id '%s' — skipping.", dim_id)
            continue

        if ai_rating not in VALID_RATINGS:
            logger.warning("AI returned invalid rating '%s' for %s — defaulting to NEE.", ai_rating, dim_id)
            ai_rating = "Not Enough Evidence"

        look_fors_raw = item.get("look_fors", [])
        if isinstance(look_fors_raw, str):
            look_fors_raw = [look_fors_raw]

        result.dimensions.append(
            DimensionResult(
                dimension_id=dim_id,
                dimension_name=DIMENSIONS[dim_id],
                ai_rating=ai_rating,
                user_rating=ai_rating,  # starts same as AI rating
                rating_numeric=RATING_NUMERIC.get(ai_rating, 0.0),
                evidence=str(item.get("evidence", "Not Enough Evidence")).strip(),
                why_this_rating=str(item.get("why_this_rating", "Not Enough Evidence")).strip(),
                glow=str(item.get("glow", "Not Enough Evidence")).strip(),
                grow=str(item.get("grow", "Not Enough Evidence")).strip(),
                action_step=str(item.get("action_step", "Not Enough Evidence")).strip(),
                look_fors=look_fors_raw,
            )
        )

    result.compute_scores()
    return result


# ---------------------------------------------------------------------------
# OpenAI API caller  (reads OPENAI_API_KEY from .env or environment)
# ---------------------------------------------------------------------------

def _load_api_key() -> str:
    """
    Resolve OPENAI_API_KEY in priority order:
      1. Already set in os.environ (e.g. shell export or CI secret)
      2. .env file — searched upward from generator.py until found
      3. config.settings.settings.OPENAI_API_KEY (legacy fallback)
    """
    # 1. Already in environment
    key = os.environ.get("OPENAI_API_KEY", "")
    if key:
        return key

    # 2. Walk upward to find a .env file and load it
    try:
        from dotenv import load_dotenv
        search_dir = Path(__file__).resolve().parent
        for _ in range(8):
            env_file = search_dir / ".env"
            if env_file.is_file():
                load_dotenv(dotenv_path=env_file, override=False)
                logger.info("Loaded .env from %s", env_file)
                break
            search_dir = search_dir.parent
        key = os.environ.get("OPENAI_API_KEY", "")
        if key:
            return key
    except ImportError:
        logger.warning("python-dotenv not installed; skipping .env loading.")

    # 3. Legacy settings fallback
    try:
        from config.settings import settings
        key = getattr(settings, "OPENAI_API_KEY", "")
        if key:
            return key
    except Exception:
        pass

    raise EnvironmentError(
        "OPENAI_API_KEY is not set.\n"
        "Add it to your .env file:  OPENAI_API_KEY=sk-...\n"
        "or export it as an environment variable before running."
    )


def _call_openai(system: str, user: str) -> str:
    import openai

    api_key = _load_api_key()
    client = openai.OpenAI(api_key=api_key)

    logger.info("Calling OpenAI (gpt-4o)")
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        max_tokens=16000,
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    choice = response.choices[0]
    finish_reason = choice.finish_reason
    logger.info("OpenAI finish_reason: %s", finish_reason)
    return choice.message.content or ""


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def generate_coaching_result(data: ObservationData) -> CoachingResult:
    """
    Validate observation data, call Claude, and return a CoachingResult.
    AI autonomously assigns ratings based only on observation evidence.
    """
    if not data.teacher_name or not data.teacher_name.strip():
        raise ValueError("Teacher name is required.")
    if not data.observation_notes or len(data.observation_notes.strip()) < 30:
        raise ValueError(
            "Observation notes must be at least 30 characters to generate meaningful AI feedback."
        )
    if not data.selected_domains:
        raise ValueError("Please select at least one domain to evaluate.")

    user_prompt = _build_user_prompt(data)
    logger.info("Calling OpenAI for teacher=%s", data.teacher_name)

    raw_content = _call_openai(_SYSTEM_PROMPT, user_prompt)

    logger.info("Raw AI response (first 1000): %s", raw_content[:1000])

    # Strip markdown fences if present
    content = raw_content.strip()
    if content.startswith("```"):
        content = content.split("```", 2)[-1] if content.count("```") >= 2 else content
        content = content.lstrip("json").strip()
        if content.endswith("```"):
            content = content[:-3].strip()

    return _parse_response(content, data)

def rewrite_coaching_result(
    result: CoachingResult,
    data: ObservationData,
    manual_ratings: dict[str, str],
) -> CoachingResult:
    user_prompt = _build_user_prompt(data, manual_ratings=manual_ratings)
    logger.info("Rewriting report for teacher=%s overrides=%s", data.teacher_name, manual_ratings)

    raw_content = _call_openai(_SYSTEM_PROMPT, user_prompt)

    content = raw_content.strip()
    if content.startswith("```"):
        content = content.split("```", 2)[-1] if content.count("```") >= 2 else content
        content = content.lstrip("json").strip()
        if content.endswith("```"):
            content = content[:-3].strip()

    try:
        payload: dict[str, Any] = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"AI rewrite response is not valid JSON: {content[:300]}") from exc

    # AI থেকে আসা updated dimensions lookup বানাও
    updated_dims: dict[str, dict] = {}
    for item in payload.get("dimensions", []):
        dim_id = str(item.get("dimension_id", "")).strip()
        if dim_id:
            updated_dims[dim_id] = item

    new_result = CoachingResult(
        teacher_name=result.teacher_name,
        date=result.date,
        raw_notes_summary=payload.get("raw_notes_summary", result.raw_notes_summary),
    )

    processed_ids = set()

    # DB তে যা আছে সেগুলো process করো
    for dim in result.dimensions:
        processed_ids.add(dim.dimension_id)
        new_rating = manual_ratings.get(dim.dimension_id, dim.user_rating)
        item = updated_dims.get(dim.dimension_id, {})
        look_fors_raw = item.get("look_fors", dim.look_fors)
        if isinstance(look_fors_raw, str):
            look_fors_raw = [look_fors_raw]

        new_result.dimensions.append(
            DimensionResult(
                dimension_id=dim.dimension_id,
                dimension_name=dim.dimension_name,
                ai_rating=dim.ai_rating,
                user_rating=new_rating,
                rating_numeric=RATING_NUMERIC.get(new_rating, 0.0),
                evidence=str(item.get("evidence", dim.evidence)).strip(),
                why_this_rating=str(item.get("why_this_rating", dim.why_this_rating)).strip(),
                glow=str(item.get("glow", dim.glow)).strip(),
                grow=str(item.get("grow", dim.grow)).strip(),
                action_step=str(item.get("action_step", dim.action_step)).strip(),
                look_fors=look_fors_raw,
            )
        )

    # AI নতুন dimension return করলে সেগুলোও যোগ করো
    for dim_id, item in updated_dims.items():
        if dim_id not in processed_ids and dim_id in DIMENSIONS:
            new_rating = manual_ratings.get(dim_id, str(item.get("ai_rating", "Not Enough Evidence")))
            look_fors_raw = item.get("look_fors", [])
            if isinstance(look_fors_raw, str):
                look_fors_raw = [look_fors_raw]

            new_result.dimensions.append(
                DimensionResult(
                    dimension_id=dim_id,
                    dimension_name=DIMENSIONS[dim_id],
                    ai_rating=str(item.get("ai_rating", "Not Enough Evidence")),
                    user_rating=new_rating,
                    rating_numeric=RATING_NUMERIC.get(new_rating, 0.0),
                    evidence=str(item.get("evidence", "")).strip(),
                    why_this_rating=str(item.get("why_this_rating", "")).strip(),
                    glow=str(item.get("glow", "")).strip(),
                    grow=str(item.get("grow", "")).strip(),
                    action_step=str(item.get("action_step", "")).strip(),
                    look_fors=look_fors_raw,
                )
            )

    new_result.compute_scores()
    return new_result