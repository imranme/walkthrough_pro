"""
generator.py
------------
AI Coaching Result Generator for the T-TESS Observation Tool.

Responsibilities
----------------
1. Validate raw observation form data.
2. Build a structured prompt aligned with the T-TESS rubric dimensions.
3. Call the OpenAI API and parse the JSON response.
4. Return a strongly-typed ``CoachingResult`` object.

T-TESS Dimensions covered
--------------------------
Domain 2 – Classroom Environment
    2.1  Creating an Environment of Respect
    2.2  Establishing a Culture for Learning
    2.3  Managing Classroom Procedures
    2.4  Managing Student Behavior

Domain 3 – Instruction
    3.1  Communicating with Students
    3.2  Using Questioning and Discussion
    3.3  Engaging Students in Learning
    3.4  Using Assessment in Instruction
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import openai

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
# Layout:
#   <project_root>/
#       app/
#           common/
#           components/
#               generator.py   ← THIS file
#           config/
#           frontend/
#       .env
#
# We walk upward from __file__ until we find the folder that contains
# `common/` (that is `app/`) and add it to sys.path.
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve()
_APP_DIR = _HERE.parent        # start: app/components/
for _ in range(6):             # safety guard
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
)
from config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — match EXACTLY what the Figma form shows
# ---------------------------------------------------------------------------

# Domain 2: Classroom Environment
# Domain 3: Instruction
DIMENSIONS: dict[str, str] = {
    "2.1": "Creating an Environment of Respect",
    "2.2": "Establishing a Culture for Learning",
    "2.3": "Managing Classroom Procedures",
    "2.4": "Managing Student Behavior",
    "3.1": "Communicating with Students",
    "3.2": "Using Questioning and Discussion",
    "3.3": "Engaging Students in Learning",
    "3.4": "Using Assessment in Instruction",
}

DOMAIN_DIMENSION_MAP: dict[str, list[str]] = {
    "Domain 2 - Classroom Environment": ["2.1", "2.2", "2.3", "2.4"],
    "Domain 3 - Instruction":           ["3.1", "3.2", "3.3", "3.4"],
}

VALID_RATINGS = {
    "Distinguished",
    "Accomplished",
    "Proficient",
    "Developing",
    "Improvement Needed",
}

RATING_NUMERIC: dict[str, float] = {
    "Distinguished":      4.0,
    "Accomplished":       3.5,
    "Proficient":         3.0,
    "Developing":         2.0,
    "Improvement Needed": 1.0,
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ObservationData:
    """Input payload representing a completed observation form."""

    teacher_name: str
    subject:      str
    grade_level:  str
    date:         str
    time:         str
    observation_notes: str

    # Domain 2 – Classroom Environment sub-scores (1.0–4.0, entered by observer)
    d2_creating_environment:   float = 3.0   # 2.1 Creating an Environment of Respect
    d2_culture_for_learning:   float = 3.0   # 2.2 Establishing a Culture for Learning
    d2_classroom_procedures:   float = 3.0   # 2.3 Managing Classroom Procedures
    d2_student_behavior:       float = 3.0   # 2.4 Managing Student Behavior

    # Domain 3 – Instruction sub-scores (1.0–4.0, entered by observer)
    d3_communicating_students: float = 3.0   # 3.1 Communicating with Students
    d3_questioning_discussion: float = 3.0   # 3.2 Using Questioning and Discussion
    d3_engaging_learning:      float = 3.0   # 3.3 Engaging Students in Learning
    d3_assessment_instruction: float = 3.0   # 3.4 Using Assessment in Instruction


@dataclass
class DimensionResult:
    """AI-generated coaching output for a single T-TESS dimension."""

    dimension_id:       str    # e.g. "2.1"
    dimension_name:     str    # e.g. "Creating an Environment of Respect"
    observer_score:     float  # raw score entered by observer (1.0–4.0)
    rating:             str    # one of VALID_RATINGS (AI-assigned)
    rating_numeric:     float  # numeric from RATING_NUMERIC
    coaching_feedback:  str    # 2–3 sentence evidence-based coaching note
    growth_suggestion:  str    # 1–2 actionable next steps


@dataclass
class CoachingResult:
    """Full AI coaching output for one observation."""

    teacher_name:       str
    date:               str
    raw_notes_summary:  str                        # ~3-sentence lesson summary

    dimensions: list[DimensionResult] = field(default_factory=list)

    # Computed after dimensions are populated
    domain_scores:  dict[str, float] = field(default_factory=dict)
    overall_score:  float = 0.0

    def compute_scores(self) -> None:
        """Calculate domain averages and overall score from AI rating numerics."""
        domain_sums: dict[str, list[float]] = {d: [] for d in DOMAIN_DIMENSION_MAP}

        for dim in self.dimensions:
            for domain, dim_ids in DOMAIN_DIMENSION_MAP.items():
                if dim.dimension_id in dim_ids:
                    domain_sums[domain].append(dim.rating_numeric)

        self.domain_scores = {
            domain: round(sum(scores) / len(scores), 1) if scores else 0.0
            for domain, scores in domain_sums.items()
        }

        all_scores = [s for scores in domain_sums.values() for s in scores]
        self.overall_score = (
            round(sum(all_scores) / len(all_scores), 1) if all_scores else 0.0
        )


# ---------------------------------------------------------------------------
# System prompt — aligned to Figma domain/sub-item names
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """
You are an expert instructional coach certified in the Texas Teacher Evaluation and Support System (T-TESS).
Your job is to generate structured coaching feedback for each T-TESS dimension using:
  1. The observer's numeric score (AUTHORITATIVE — you must use it exactly as given)
  2. The observation notes (EVIDENCE — only cite what is explicitly written there)
  3. The official T-TESS rubric descriptors below (LANGUAGE — use these to frame your feedback)

═══════════════════════════════════════════════════════════════
STEP 1 — RATING LABEL (mandatory, no exceptions, no overrides)
═══════════════════════════════════════════════════════════════
The user prompt will tell you the EXACT rating label for each dimension.
You MUST copy that label exactly into the "rating" field. Do not change it.

═══════════════════════════════════════════════════════════════
STEP 2 — RUBRIC DESCRIPTORS (use these to write feedback text)
═══════════════════════════════════════════════════════════════

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DIMENSION 2.1 — Creating an Environment of Respect
Goal: The teacher supports all learners in pursuit of high levels of academic and social-emotional success.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Distinguished:      Provides opportunities for students to establish high academic AND social-emotional expectations for themselves. Persists until ALL students demonstrate mastery. Provides opportunities for students to self-monitor and self-correct mistakes. Systematically enables students to set goals and monitor progress over time.
  Accomplished:       Provides opportunities for students to establish high expectations. Persists until MOST students show mastery. Anticipates student mistakes and encourages avoiding learning pitfalls. Establishes systems for student initiative and self-monitoring.
  Proficient:         Sets academic expectations challenging ALL students. Persists until most students show mastery. Addresses mistakes and follows through to ensure mastery. Provides opportunities for student initiative.
  Developing:         Sets expectations challenging MOST students. Persists until SOME students show mastery. Sometimes addresses mistakes. Sometimes provides initiative opportunities.
  Improvement Needed: Sets expectations challenging FEW students. Concludes lesson even when few demonstrate mastery. Allows mistakes to go unaddressed or discourages further effort. Rarely provides initiative opportunities.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DIMENSION 2.2 — Content Knowledge and Expertise
Goal: The teacher uses content and pedagogical expertise to design and execute lessons aligned with standards, related content, and student needs.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Distinguished:      Displays extensive content knowledge of all subjects taught and closely related subjects. Integrates learning objectives with other disciplines, content areas, and real-world experience. Consistently anticipates misunderstandings and proactively develops techniques to mitigate. Consistently provides varied thinking types (analytical, practical, creative, research-based). Sequences instruction to show how lesson fits discipline, standards, related content, and real-world scenarios.
  Accomplished:       Conveys depth of content knowledge allowing differentiated explanations. Integrates objectives with other disciplines and real-world experiences. Anticipates misunderstandings proactively. Regularly provides varied thinking types. Sequences instruction to show fit within discipline and standards.
  Proficient:         Conveys accurate content knowledge in multiple contexts. Integrates objectives with other disciplines. Anticipates possible misunderstandings. Provides varied thinking opportunities. Accurately reflects how lesson fits discipline and standards.
  Developing:         Conveys accurate content knowledge. Sometimes integrates with other disciplines. Sometimes anticipates misunderstandings. Sometimes provides varied thinking types.
  Improvement Needed: Conveys inaccurate content leading to student confusion. Rarely integrates disciplines. Does not anticipate misunderstandings. Provides few varied thinking opportunities.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DIMENSION 2.3 — Communication
Goal: The teacher clearly and accurately communicates to support persistence, deeper learning, and effective effort.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Distinguished:      Establishes practices encouraging ALL students to communicate safely and effectively using varied tools with teacher and peers. Uses student misunderstandings strategically to inspire exploration and discovery. Clear, coherent explanations and correct communication. Asks creative/evaluative/analysis-level questions requiring deeper understanding. Skillfully balances wait time, questioning, and student responses for student-directed learning. Skillfully provokes student-led learning of meaningful content.
  Accomplished:       Establishes practices encouraging all students to communicate effectively including visual tools and technology. Anticipates misunderstandings proactively. Clear, coherent explanations and correct communication. Asks creative/evaluative/analysis questions provoking thought and discussion. Skillfully uses probing questions to clarify, elaborate, and extend. Provides wait time.
  Proficient:         Establishes practices for MOST students to communicate with teacher and peers. Recognizes misunderstandings and responds with array of techniques. Clear explanations and correct communication. Asks remember/understand/apply questions provoking discussion. Uses probing questions to clarify and elaborate.
  Developing:         Leads lessons with SOME opportunity for dialogue, clarification, or elaboration. Recognizes misunderstandings but has limited response ability. Generally clear communication with minor grammar errors. Asks remember/understand questions that do little to amplify discussion.
  Improvement Needed: Directs lessons with LITTLE opportunity for dialogue. Sometimes unaware of or unresponsive to misunderstandings. Inaccurate grammar and written communication with errors. Rarely asks questions, or asks ones that do not amplify discussion or align to objective.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DIMENSION 2.4 — Differentiation
Goal: The teacher differentiates instruction, aligning methods and techniques to diverse student needs.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Distinguished:      Adapts lessons with WIDE VARIETY of strategies to address ALL students' individual needs. Consistently monitors quality of student participation and performance. Always provides differentiated instructional methods and content. Consistently prevents confusion or disengagement by addressing all learning and social/emotional needs.
  Accomplished:       Adapts lessons to address individual needs of ALL students. Regularly monitors quality. Regularly provides differentiated methods and content. Proactively minimizes confusion or disengagement by addressing learning and social/emotional needs of all.
  Proficient:         Adapts lessons to address individual needs of ALL students. Regularly monitors quality. Provides differentiated methods and content. Recognizes when students become confused or disengaged and responds to learning or social/emotional needs.
  Developing:         Adapts lessons to address SOME student needs. Sometimes monitors quality. Sometimes provides differentiated methods and content. Sometimes recognizes confusion/disengagement and minimally responds.
  Improvement Needed: Provides one-size-fits-all lessons without meaningful differentiation. Rarely monitors quality. Rarely provides differentiated methods. Does not recognize or appropriately respond to confusion/disengagement.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DIMENSION 3.1 — Classroom Environment, Routines, and Procedures
Goal: The teacher organizes a safe, accessible, and efficient classroom.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Distinguished:      Establishes routines, transitions, and procedures primarily relying on STUDENT leadership and responsibility. Students take primary responsibility for managing groups, supplies, and equipment. Classroom is safe and thoughtfully designed to engage, challenge, and inspire beyond learning objectives.
  Accomplished:       Establishes effective routines, transitions, and procedures implemented effortlessly. Students take SOME responsibility for managing groups, supplies, and equipment. Classroom is safe, inviting, and organized to support objectives, accessible to all students.
  Proficient:         All procedures, routines, and transitions are clear and efficient. Students actively participate in groups and manage supplies with very limited teacher direction. Classroom is safe and organized, accessible to most students.
  Developing:         MOST procedures provide clear direction but others are unclear and inefficient. Students depend on teacher for managing groups, supplies, and equipment. Classroom is safe and accessible to most but disorganized and cluttered.
  Improvement Needed: FEW procedures guide student behavior. Transitions are characterized by confusion and inefficiency. Students often do not know what is expected. Classroom is unsafe, disorganized, and uncomfortable. Some students cannot access materials.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DIMENSION 3.2 — Managing Student Behavior
Goal: The teacher establishes, communicates, and maintains clear expectations for student behavior.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Distinguished:      Consistently monitors behavior SUBTLY, reinforces positive behaviors appropriately, and intercepts misbehavior fluidly. Students AND teacher create, adopt, and maintain classroom behavior standards together.
  Accomplished:       Consistently encourages and monitors student behavior subtly and responds to misbehavior SWIFTLY. Most students know, understand, and respect classroom behavior standards.
  Proficient:         Consistently implements campus and/or classroom behavior system PROFICIENTLY. Most students meet expected classroom behavior standards.
  Developing:         INCONSISTENTLY implements campus and/or classroom behavior system. Student failure to meet behavior standards interrupts learning.
  Improvement Needed: RARELY or unfairly enforces campus or classroom behavior standards. Student behavior impedes learning in the classroom.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DIMENSION 3.3 — Classroom Culture
Goal: The teacher leads a mutually respectful and collaborative class of actively engaged learners.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Distinguished:      Consistently engages ALL students with relevant, meaningful learning based on their interests and abilities. Students collaborate positively and encourage each other's efforts and achievements. Creates positive rapport among students.
  Accomplished:       Engages ALL students with relevant, meaningful learning, sometimes adjusting based on student interests and abilities. Students collaborate positively with each other and the teacher.
  Proficient:         Engages ALL students in relevant, meaningful learning. Students work respectfully individually and in groups.
  Developing:         Establishes environment where MOST students are engaged. Students are SOMETIMES disrespectful of each other.
  Improvement Needed: Establishes environment where FEW students are engaged. Students are disrespectful of each other AND the teacher.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DIMENSION 3.4 — Monitor and Adjust
Goal: The teacher formally and informally collects, analyzes, and uses student progress data and makes needed lesson adjustments.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Distinguished:      Systematically gathers student input to monitor and adjust instruction, activities, or pacing for ALL student needs. Adjusts instruction to maintain engagement. Uses DISCREET and EXPLICIT checks for understanding through questioning and academic feedback.
  Accomplished:       Utilizes student input to monitor and adjust instruction, activities, AND pacing. Adjusts to maintain engagement. CONTINUALLY checks for understanding through purposeful questioning and feedback.
  Proficient:         CONSISTENTLY invites student input to monitor and adjust instruction and activities. Adjusts to maintain engagement. Monitors student behavior and responses for engagement and understanding.
  Developing:         SOMETIMES utilizes student input to monitor and adjust. Adjusts within a limited range. Sees student behavior but misses some signs of disengagement. Aware of most responses but misses some misunderstanding clues.
  Improvement Needed: RARELY uses student input to monitor and adjust. Persists with instruction not engaging students. Generally does not link behavior with engagement/understanding. Makes no attempts to engage disengaged students.

═══════════════════════════════════════════════════════════════
STEP 3 — HOW TO WRITE FEEDBACK
═══════════════════════════════════════════════════════════════
For EACH dimension:
  coaching_feedback (2-3 sentences):
    • Sentence 1: Cite a SPECIFIC moment from the observation notes as evidence.
    • Sentence 2: State what the assigned rating level means per the rubric descriptor above.
    • Sentence 3 (optional): Note a specific strength or specific gap at this level.

  growth_suggestion (1-2 sentences):
    • Reference the NEXT rating level descriptor as the target.
    • Give ONE concrete, classroom-ready action step directly tied to the observation notes.
    • If already Distinguished: suggest how to sustain and share this practice with colleagues.

  raw_notes_summary (3 sentences):
    • Summarize the full lesson arc from the observation notes only.
    • Do NOT fabricate any detail not present in the notes.

═══════════════════════════════════════════════════════════════
STEP 4 — OUTPUT (valid JSON only, no markdown fences, no preamble)
═══════════════════════════════════════════════════════════════
{
  "raw_notes_summary": "...",
  "dimensions": [
    { "dimension_id": "2.1", "rating": "<EXACT LABEL FROM USER PROMPT>", "coaching_feedback": "...", "growth_suggestion": "..." },
    { "dimension_id": "2.2", "rating": "<EXACT LABEL FROM USER PROMPT>", "coaching_feedback": "...", "growth_suggestion": "..." },
    { "dimension_id": "2.3", "rating": "<EXACT LABEL FROM USER PROMPT>", "coaching_feedback": "...", "growth_suggestion": "..." },
    { "dimension_id": "2.4", "rating": "<EXACT LABEL FROM USER PROMPT>", "coaching_feedback": "...", "growth_suggestion": "..." },
    { "dimension_id": "3.1", "rating": "<EXACT LABEL FROM USER PROMPT>", "coaching_feedback": "...", "growth_suggestion": "..." },
    { "dimension_id": "3.2", "rating": "<EXACT LABEL FROM USER PROMPT>", "coaching_feedback": "...", "growth_suggestion": "..." },
    { "dimension_id": "3.3", "rating": "<EXACT LABEL FROM USER PROMPT>", "coaching_feedback": "...", "growth_suggestion": "..." },
    { "dimension_id": "3.4", "rating": "<EXACT LABEL FROM USER PROMPT>", "coaching_feedback": "...", "growth_suggestion": "..." }
  ]
}
""".strip()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_observation(data: ObservationData) -> None:
    """Raise InvalidObservationDataError for missing or invalid fields."""
    if not data.teacher_name or not data.teacher_name.strip():
        raise InvalidObservationDataError(
            "Teacher name is required.", field="teacher_name"
        )
    if not data.observation_notes or len(data.observation_notes.strip()) < 30:
        raise InvalidObservationDataError(
            "Observation notes must be at least 30 characters.",
            field="observation_notes",
            detail=(
                "Provide enough detail for the AI to make evidence-based "
                "ratings across all T-TESS dimensions."
            ),
        )
    # Validate all sub-scores are in range
    sub_scores = {
        "d2_creating_environment":   data.d2_creating_environment,
        "d2_culture_for_learning":   data.d2_culture_for_learning,
        "d2_classroom_procedures":   data.d2_classroom_procedures,
        "d2_student_behavior":       data.d2_student_behavior,
        "d3_communicating_students": data.d3_communicating_students,
        "d3_questioning_discussion": data.d3_questioning_discussion,
        "d3_engaging_learning":      data.d3_engaging_learning,
        "d3_assessment_instruction": data.d3_assessment_instruction,
    }
    for field_name, val in sub_scores.items():
        if not (1.0 <= val <= 4.0):
            raise InvalidObservationDataError(
                f"{field_name} must be between 1.0 and 4.0.",
                field=field_name,
                detail=f"Received: {val}",
            )


# ---------------------------------------------------------------------------
# Observer score lookup — maps dimension_id → observer's raw slider score
# ---------------------------------------------------------------------------

def _observer_score_for(dim_id: str, data: ObservationData) -> float:
    mapping = {
        "2.1": data.d2_creating_environment,
        "2.2": data.d2_culture_for_learning,
        "2.3": data.d2_classroom_procedures,
        "2.4": data.d2_student_behavior,
        "3.1": data.d3_communicating_students,
        "3.2": data.d3_questioning_discussion,
        "3.3": data.d3_engaging_learning,
        "3.4": data.d3_assessment_instruction,
    }
    return mapping.get(dim_id, 3.0)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _score_to_label(score: float) -> str:
    """
    Convert a 1.0-4.0 observer score to the exact T-TESS rating label.
    Thresholds divide the 1-4 scale into 5 equal bands:
      4.0        = Distinguished
      3.5 - 3.99 = Distinguished
      2.8 - 3.49 = Accomplished
      2.1 - 2.79 = Proficient
      1.4 - 2.09 = Developing
      1.0 - 1.39 = Improvement Needed
    """
    if score >= 3.5:
        return "Distinguished"
    elif score >= 2.8:
        return "Accomplished"
    elif score >= 2.1:
        return "Proficient"
    elif score >= 1.4:
        return "Developing"
    else:
        return "Improvement Needed"


def _build_user_prompt(data: ObservationData) -> str:
    # Pre-compute labels in Python so the AI never needs to do the conversion
    s21 = data.d2_creating_environment
    s22 = data.d2_culture_for_learning
    s23 = data.d2_classroom_procedures
    s24 = data.d2_student_behavior
    s31 = data.d3_communicating_students
    s32 = data.d3_questioning_discussion
    s33 = data.d3_engaging_learning
    s34 = data.d3_assessment_instruction

    lines = [
        f"Teacher : {data.teacher_name}",
        f"Subject : {data.subject}",
        f"Grade   : {data.grade_level}",
        f"Date    : {data.date}",
        f"Time    : {data.time}",
        "",
        "=== Observer Scores (USE THESE EXACT RATING LABELS — do not change them) ===",
        "  2.1 Creating an Environment of Respect    : " + f"{s21:.1f}" + " / 4.0  →  rating MUST be " + _score_to_label(s21),
        "  2.2 Establishing a Culture for Learning   : " + f"{s22:.1f}" + " / 4.0  →  rating MUST be " + _score_to_label(s22),
        "  2.3 Managing Classroom Procedures         : " + f"{s23:.1f}" + " / 4.0  →  rating MUST be " + _score_to_label(s23),
        "  2.4 Managing Student Behavior             : " + f"{s24:.1f}" + " / 4.0  →  rating MUST be " + _score_to_label(s24),
        "  3.1 Communicating with Students           : " + f"{s31:.1f}" + " / 4.0  →  rating MUST be " + _score_to_label(s31),
        "  3.2 Using Questioning and Discussion      : " + f"{s32:.1f}" + " / 4.0  →  rating MUST be " + _score_to_label(s32),
        "  3.3 Engaging Students in Learning         : " + f"{s33:.1f}" + " / 4.0  →  rating MUST be " + _score_to_label(s33),
        "  3.4 Using Assessment in Instruction       : " + f"{s34:.1f}" + " / 4.0  →  rating MUST be " + _score_to_label(s34),
        "",
        "IMPORTANT: Your coaching_feedback and growth_suggestion for each dimension must be",
        "grounded in specific events from the observation notes below AND the rubric descriptor",
        "for the assigned rating level. Do not write generic feedback.",
        "",
        "=== Observation Notes ===",
        data.observation_notes.strip(),
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def _parse_response(
    raw_json: str,
    data: ObservationData,
) -> CoachingResult:
    """Parse the JSON string from the model into a CoachingResult."""
    try:
        payload: dict[str, Any] = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise RubricParsingError(
            "OpenAI response is not valid JSON.",
            detail=f"Raw response (first 300 chars): {raw_json[:300]}",
        ) from exc

    summary = payload.get("raw_notes_summary", "").strip()
    if not summary:
        raise RubricParsingError("Missing 'raw_notes_summary' in AI response.")

    result = CoachingResult(
        teacher_name=data.teacher_name,
        date=data.date,
        raw_notes_summary=summary,
    )

    raw_dims: list[dict] = payload.get("dimensions", [])
    if not raw_dims:
        raise RubricParsingError("AI response contains no 'dimensions' array.")

    for item in raw_dims:
        dim_id = str(item.get("dimension_id", "")).strip()
        rating = str(item.get("rating", "")).strip()

        if dim_id not in DIMENSIONS:
            logger.warning("Unrecognised dimension_id '%s' — skipping.", dim_id)
            continue

        # If AI returned wrong label, override with the correct one from observer score
        observer_score = _observer_score_for(dim_id, data)
        expected_rating = _score_to_label(observer_score)
        if rating not in VALID_RATINGS or rating != expected_rating:
            logger.warning(
                "AI returned rating '%s' for %s but expected '%s' — overriding.",
                rating, dim_id, expected_rating
            )
            rating = expected_rating

        result.dimensions.append(
            DimensionResult(
                dimension_id=dim_id,
                dimension_name=DIMENSIONS[dim_id],
                observer_score=observer_score,
                rating=rating,
                rating_numeric=RATING_NUMERIC[rating],
                coaching_feedback=str(item.get("coaching_feedback", "")).strip(),
                growth_suggestion=str(item.get("growth_suggestion", "")).strip(),
            )
        )

    missing = set(DIMENSIONS) - {d.dimension_id for d in result.dimensions}
    if missing:
        logger.warning("AI response is missing dimensions: %s", sorted(missing))

    result.compute_scores()
    return result


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_coaching_result(data: ObservationData) -> CoachingResult:
    """
    Validate observation data, call OpenAI, and return a CoachingResult.

    Raises
    ------
    ConfigurationError          OPENAI_API_KEY not set.
    InvalidObservationDataError Form data fails validation.
    OpenAIRateLimitError        API returns 429.
    OpenAITimeoutError          Request times out.
    OpenAIClientError           Any other OpenAI API error.
    RubricParsingError          AI response cannot be parsed.
    """
    try:
        settings.validate()
    except ValueError as exc:
        raise ConfigurationError(str(exc)) from exc

    _validate_observation(data)

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user",   "content": _build_user_prompt(data)},
    ]

    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    logger.info("Calling OpenAI model=%s teacher=%s", settings.OPENAI_MODEL, data.teacher_name)

    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            max_tokens=settings.OPENAI_MAX_TOKENS,
            temperature=settings.OPENAI_TEMPERATURE,
            response_format={"type": "json_object"},
        )
    except openai.RateLimitError as exc:
        raise OpenAIRateLimitError(
            "OpenAI rate limit reached. Please wait and try again.", cause=exc
        ) from exc
    except openai.APITimeoutError as exc:
        raise OpenAITimeoutError(
            "The request to OpenAI timed out. Please try again.", cause=exc
        ) from exc
    except openai.AuthenticationError as exc:
        raise ConfigurationError(
            "OpenAI authentication failed. Check your OPENAI_API_KEY.",
            detail=str(exc),
        ) from exc
    except openai.OpenAIError as exc:
        raise OpenAIClientError(
            "An unexpected OpenAI API error occurred.",
            detail=str(exc),
            cause=exc,
        ) from exc

    raw_content = response.choices[0].message.content or ""
    logger.debug("Raw AI response: %s", raw_content[:500])

    return _parse_response(raw_content, data)