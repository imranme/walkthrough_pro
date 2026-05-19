"""
apps/observations/ai_service.py
────────────────────────────────
STEP 1 → generate_initial_feedback()   (Form Submission)
STEP 2 → rewrite_feedback()            (After Rating Adjustments)
"""

import logging
logger = logging.getLogger(__name__)


def generate_initial_feedback(observation_data: dict) -> dict:
    try:
        from app.components.generator import (
            ObservationData,
            generate_coaching_result,
            DOMAIN_DIMENSION_MAP,
        )

        raw_domains = observation_data.get("selected_domains", [])
        matched_domains = [d for d in raw_domains if d in DOMAIN_DIMENSION_MAP]
        if not matched_domains:
            matched_domains = list(DOMAIN_DIMENSION_MAP.keys())

        obs = ObservationData(
            teacher_name      = observation_data.get("teacher_name", ""),
            subject           = observation_data.get("subject", ""),
            grade_level       = observation_data.get("grade_level", ""),
            date              = str(observation_data.get("observation_date", "")),
            time              = str(observation_data.get("observation_time", "")),
            observation_notes = observation_data.get("raw_notes", ""),
            selected_domains  = matched_domains,
        )

        result = generate_coaching_result(obs)
        return _result_to_dict(result)

    except Exception as exc:
        logger.error("AI initial feedback error: %s", exc, exc_info=True)
        return {
            "overall_score":     0.0,
            "domain_scores":     {},
            "raw_notes_summary": "",
            "dimensions":        [],
            "error":             str(exc),
        }


def rewrite_feedback(
    observation_data: dict,
    original_result_dict: dict,
    override_ratings: dict,
) -> dict:
    try:
        from app.components.generator import (
            ObservationData,
            CoachingResult,
            DimensionResult,
            DIMENSIONS,
            RATING_NUMERIC,
            DOMAIN_DIMENSION_MAP,
            rewrite_coaching_result,
        )

        # Rewrite এ সবসময় সব domain evaluate করতে হবে
        all_domains = list(DOMAIN_DIMENSION_MAP.keys())

        obs = ObservationData(
            teacher_name      = observation_data.get("teacher_name", ""),
            subject           = observation_data.get("subject", ""),
            grade_level       = observation_data.get("grade_level", ""),
            date              = str(observation_data.get("observation_date", "")),
            time              = str(observation_data.get("observation_time", "")),
            observation_notes = observation_data.get("raw_notes", ""),
            selected_domains  = all_domains,
        )

        result_dict = original_result_dict if isinstance(original_result_dict, dict) else {}

        # DB থেকে আসা previous result rebuild করা
        prev_result = CoachingResult(
            teacher_name      = obs.teacher_name,
            date              = obs.date,
            raw_notes_summary = result_dict.get("raw_notes_summary", ""),
        )

        for dim in result_dict.get("dimensions", []):
            dim_id      = dim.get("dimension_id", "")
            ai_rating   = dim.get("ai_rating", dim.get("rating", "Not Enough Evidence"))
            user_rating = dim.get("user_rating", ai_rating)
            look_fors   = dim.get("look_fors", [])
            if isinstance(look_fors, str):
                look_fors = [look_fors]

            prev_result.dimensions.append(
                DimensionResult(
                    dimension_id    = dim_id,
                    dimension_name  = DIMENSIONS.get(dim_id, ""),
                    ai_rating       = ai_rating,
                    user_rating     = user_rating,
                    rating_numeric  = RATING_NUMERIC.get(user_rating, 0.0),
                    evidence        = dim.get("evidence", ""),
                    why_this_rating = dim.get("why_this_rating", ""),
                    glow            = dim.get("glow", ""),
                    grow            = dim.get("grow", ""),
                    action_step     = dim.get("action_step", ""),
                    look_fors       = look_fors,
                )
            )

        new_result = rewrite_coaching_result(
            result         = prev_result,
            data           = obs,
            manual_ratings = override_ratings if isinstance(override_ratings, dict) else {},
        )

        return _result_to_dict(new_result)

    except Exception as exc:
        logger.error("AI rewrite error: %s", exc, exc_info=True)
        return {
            "overall_score":     0.0,
            "domain_scores":     {},
            "raw_notes_summary": "",
            "dimensions":        [],
            "error":             str(exc),
        }


def _result_to_dict(result) -> dict:
    dimensions = []
    for d in result.dimensions:
        look_fors = d.look_fors
        if isinstance(look_fors, str):
            look_fors = [look_fors]
        dimensions.append({
            "dimension_id":    d.dimension_id,
            "dimension_name":  d.dimension_name,
            "ai_rating":       d.ai_rating,
            "user_rating":     d.user_rating,
            "rating_numeric":  d.rating_numeric,
            "evidence":        d.evidence,
            "why_this_rating": d.why_this_rating,
            "glow":            d.glow,
            "grow":            d.grow,
            "action_step":     d.action_step,
            "look_fors":       look_fors,
        })

    return {
        "overall_score":     result.overall_score,
        "domain_scores":     result.domain_scores,
        "raw_notes_summary": result.raw_notes_summary,
        "dimensions":        dimensions,
    }


# Legacy wrappers
class ObservationAIService:
    @staticmethod
    def get_ai_feedback(observation_data=None, **kwargs):
        data = observation_data if isinstance(observation_data, dict) else {}
        return generate_initial_feedback(data)


def generate_feedback(observation_data: dict) -> dict:
    return generate_initial_feedback(observation_data)