# import logging
# import sys
# from pathlib import Path
# from app.components.generator import ObservationData, generate_coaching_result

# logger = logging.getLogger(__name__)

# # ১. পাথ সেটআপ
# CURRENT_FILE = Path(__file__).resolve()
# ROOT_DIR = CURRENT_FILE.parent.parent.parent
# if str(ROOT_DIR) not in sys.path:
#     sys.path.insert(0, str(ROOT_DIR))

# class ObservationAIService:
#     @staticmethod
#     def get_ai_feedback(observation_data=None, ratings=None, extra_data=None, **kwargs):
#         """
#         এখানে **kwargs যোগ করা হয়েছে যাতে 'raw_notes' বা অন্য যেকোনো 
#         unexpected keyword argument আসলেও এরর না দেয়।
#         """
#         # যদি ভিউ থেকে সরাসরি raw_notes পাঠানো হয়, সেটাকে ডিকশনারিতে নিয়ে নেওয়া
#         data = observation_data if isinstance(observation_data, dict) else {}
        
#         # যদি আর্গুমেন্ট হিসেবে raw_notes আলাদাভাবে আসে (যা তোমার এরর বলছে)
#         if 'raw_notes' in kwargs:
#             data['raw_notes'] = kwargs['raw_notes']
        
#         if extra_data:
#             data.update(extra_data)

#         return generate_feedback(data)

# def generate_feedback(observation_data: dict) -> dict:
#     """
#     আসল AI জেনারেটর লজিক (যা তোমার app.components কল করবে)
#     """
#     try:
#         from app.components.generator import ObservationData, generate_coaching_result
        
#         # ডাটা ম্যাপিং
#         obs = ObservationData(
#         teacher_name      = observation_data.get("teacher_name", "Teacher"),
#         subject           = observation_data.get("subject", ""),
#         grade_level       = observation_data.get("grade_level", ""),
#         date              = str(observation_data.get("observation_date", "")),
#         time              = str(observation_data.get("observation_time", "")),
#         observation_notes = observation_data.get("raw_notes", ""),

#         # ── FIXED: views.py থেকে আসা exact key names ──────────────────
#         d2_creating_environment   = float(observation_data.get("respect_env_score",       0) or 3.0),
#         d2_culture_for_learning   = float(observation_data.get("culture_learning_score",  0) or 3.0),
#         d2_classroom_procedures   = float(observation_data.get("classroom_proc_score",    0) or 3.0),
#         d2_student_behavior       = float(observation_data.get("student_behavior_score",  0) or 3.0),
#         d3_communicating_students = float(observation_data.get("comm_students_score",     0) or 3.0),
#         d3_questioning_discussion = float(observation_data.get("questioning_score",       0) or 3.0),
#         d3_engaging_learning      = float(observation_data.get("engaging_students_score", 0) or 3.0),
#         d3_assessment_instruction = float(observation_data.get("assessment_score",        0) or 3.0),
# )

#         result = generate_coaching_result(obs)

#         if not result:
#             raise ValueError("AI Generator returned None")

#         dimensions = []
#         if hasattr(result, 'dimensions'):
#             for d in result.dimensions:
#                 dimensions.append({
#                     "dimension_id": getattr(d, 'dimension_id', "N/A"),
#                     "rating": getattr(d, 'rating', "N/A"),
#                     "coaching_feedback": getattr(d, 'coaching_feedback', ""),
#                     "growth_suggestion": getattr(d, 'growth_suggestion', ""),
#                 })

#         return {
#             "overall_score": getattr(result, 'overall_score', 0.0),
#             "raw_notes_summary": getattr(result, 'raw_notes_summary', ""),
#             "glow": getattr(result, 'glow', "Well performed lesson."),
#             "grow": getattr(result, 'grow', "Focus on student-led transitions."),
#             "dimensions": dimensions
#         }

#     except Exception as e:
#         logger.error(f"❌ AI ERROR: {str(e)}")
#         # ব্যাকআপ রেসপন্স
#         score = float(observation_data.get("overall_performance_score", 3.0))
#         rating = "Distinguished" if score >= 3.5 else "Accomplished"
        
#         return {
#             "glow": f"Based on T-TESS descriptors, your {rating} lesson showed strong clarity.",
#             "grow": "Focus on Dimension 3.1 to improve individual student pacing.",
#             "raw_notes_summary": "Summary based on raw notes provided.",
#             "dimensions": [],
#             "error_info": str(e) # ডিবাগিং এর জন্য
#         } 

"""
apps/observations/ai_service.py  —  FINAL
══════════════════════════════════════════
generator.py এর exact mapping অনুযায়ী সব field সঠিকভাবে pass করা হচ্ছে।

generator.py mapping:
  d2_creating_environment   → 2.1 Creating an Environment of Respect
  d2_culture_for_learning   → 2.2 Establishing a Culture for Learning
  d2_classroom_procedures   → 2.3 Managing Classroom Procedures
  d2_student_behavior       → 2.4 Managing Student Behavior
  d3_communicating_students → 3.1 Communicating with Students
  d3_questioning_discussion → 3.2 Using Questioning and Discussion
  d3_engaging_learning      → 3.3 Engaging Students in Learning
  d3_assessment_instruction → 3.4 Using Assessment in Instruction

views.py থেকে আসা field names → generator.py field names:
  respect_env_score       → d2_creating_environment
  culture_learning_score  → d2_culture_for_learning
  classroom_proc_score    → d2_classroom_procedures
  student_behavior_score  → d2_student_behavior
  comm_students_score     → d3_communicating_students
  questioning_score       → d3_questioning_discussion
  engaging_students_score → d3_engaging_learning
  assessment_score        → d3_assessment_instruction
"""

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class ObservationAIService:
    @staticmethod
    def get_ai_feedback(observation_data=None, **kwargs):
        data = observation_data if isinstance(observation_data, dict) else {}
        if 'raw_notes' in kwargs:
            data['raw_notes'] = kwargs['raw_notes']
        return generate_feedback(data)


def generate_feedback(observation_data: dict) -> dict:
    """
    views.py থেকে observation data নিয়ে generator.py-তে pass করে।

    Input keys (views.py থেকে আসে):
      teacher_name, subject, grade_level,
      observation_date, observation_time, raw_notes,
      respect_env_score, culture_learning_score,
      classroom_proc_score, student_behavior_score,
      comm_students_score, questioning_score,
      engaging_students_score, assessment_score

    Output:
      overall_score, raw_notes_summary, domain_scores,
      glow, grow, dimensions
    """
    try:
        from app.components.generator import ObservationData, generate_coaching_result

        # ── Scores extract with validation ────────────────────────────
        def get_score(key: str) -> float:
            """
            Score নেওয়ার সময় ensure করি 1.0–4.0 range-এ আছে।
            0 বা None আসলে 3.0 default।
            """
            val = observation_data.get(key, 0)
            try:
                score = float(val) if val else 0.0
            except (TypeError, ValueError):
                score = 0.0
            # 0 বা valid range-এর বাইরে হলে default 3.0
            if score < 1.0 or score > 4.0:
                score = 3.0
            return score

        # ── generator.py এর ObservationData build ────────────────────
        obs = ObservationData(
            teacher_name      = observation_data.get("teacher_name", ""),
            subject           = observation_data.get("subject", ""),
            grade_level       = observation_data.get("grade_level", ""),
            date              = str(observation_data.get("observation_date", "")),
            time              = str(observation_data.get("observation_time", "")),
            observation_notes = observation_data.get("raw_notes", ""),

            # ── EXACT mapping: views.py field → generator.py field ────
            d2_creating_environment   = get_score("respect_env_score"),       # 2.1
            d2_culture_for_learning   = get_score("culture_learning_score"),  # 2.2
            d2_classroom_procedures   = get_score("classroom_proc_score"),    # 2.3
            d2_student_behavior       = get_score("student_behavior_score"),  # 2.4
            d3_communicating_students = get_score("comm_students_score"),     # 3.1
            d3_questioning_discussion = get_score("questioning_score"),       # 3.2
            d3_engaging_learning      = get_score("engaging_students_score"), # 3.3
            d3_assessment_instruction = get_score("assessment_score"),        # 3.4
        )

        # ── Log করি কোন scores পাঠাচ্ছি (debug-এর জন্য) ──────────────
        logger.info(
            "AI call → teacher=%s | scores: 2.1=%.1f 2.2=%.1f 2.3=%.1f 2.4=%.1f "
            "3.1=%.1f 3.2=%.1f 3.3=%.1f 3.4=%.1f",
            obs.teacher_name,
            obs.d2_creating_environment,
            obs.d2_culture_for_learning,
            obs.d2_classroom_procedures,
            obs.d2_student_behavior,
            obs.d3_communicating_students,
            obs.d3_questioning_discussion,
            obs.d3_engaging_learning,
            obs.d3_assessment_instruction,
        )

        # ── AI call ───────────────────────────────────────────────────
        result = generate_coaching_result(obs)

        if not result:
            raise ValueError("generate_coaching_result returned None")

        # ── dimensions list build ─────────────────────────────────────
        dimensions = []
        for d in result.dimensions:
            dimensions.append({
                "dimension_id":      d.dimension_id,
                "rating":            d.rating,
                "observer_score":    d.observer_score,
                "coaching_feedback": d.coaching_feedback,
                "growth_suggestion": d.growth_suggestion,
            })

        # ── Glow = highest rated, Grow = lowest rated ─────────────────
        if result.dimensions:
            sorted_dims = sorted(
                result.dimensions,
                key=lambda d: d.rating_numeric,
                reverse=True,
            )
            glow = sorted_dims[0].coaching_feedback
            grow = sorted_dims[-1].growth_suggestion
        else:
            glow = ""
            grow = ""

        return {
            "overall_score":     result.overall_score,
            "raw_notes_summary": result.raw_notes_summary,
            "domain_scores":     result.domain_scores,
            "glow":              glow,
            "grow":              grow,
            "dimensions":        dimensions,
        }

    except Exception as exc:
        logger.error("AI ERROR: %s", exc)
        return {
            "overall_score":     0.0,
            "raw_notes_summary": "",
            "domain_scores":     {},
            "glow":              "",
            "grow":              "",
            "dimensions":        [],
            "error":             str(exc),
        }