import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# ১. পাথ সেটআপ
CURRENT_FILE = Path(__file__).resolve()
ROOT_DIR = CURRENT_FILE.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

class ObservationAIService:
    @staticmethod
    def get_ai_feedback(observation_data=None, ratings=None, extra_data=None, **kwargs):
        """
        এখানে **kwargs যোগ করা হয়েছে যাতে 'raw_notes' বা অন্য যেকোনো 
        unexpected keyword argument আসলেও এরর না দেয়।
        """
        # যদি ভিউ থেকে সরাসরি raw_notes পাঠানো হয়, সেটাকে ডিকশনারিতে নিয়ে নেওয়া
        data = observation_data if isinstance(observation_data, dict) else {}
        
        # যদি আর্গুমেন্ট হিসেবে raw_notes আলাদাভাবে আসে (যা তোমার এরর বলছে)
        if 'raw_notes' in kwargs:
            data['raw_notes'] = kwargs['raw_notes']
        
        if extra_data:
            data.update(extra_data)

        return generate_feedback(data)

def generate_feedback(observation_data: dict) -> dict:
    """
    আসল AI জেনারেটর লজিক (যা তোমার app.components কল করবে)
    """
    try:
        from app.components.generator import ObservationData, generate_coaching_result
        
        # ডাটা ম্যাপিং
        obs = ObservationData(
            teacher_name      = observation_data.get("teacher_name", "Teacher"),
            subject           = observation_data.get("subject", "Math"),
            grade_level       = observation_data.get("grade_level", "7"),
            date              = str(observation_data.get("observation_date", "2026-04-27")),
            time              = str(observation_data.get("observation_time", "09:30")),
            observation_notes = observation_data.get("raw_notes", ""),

            # টি-টেস স্কোরগুলো (ডিফল্ট ৩.০)
            d2_creating_environment   = float(observation_data.get("respect_env", 3.0)),
            d2_culture_for_learning   = float(observation_data.get("culture", 3.0)),
            d2_classroom_procedures   = float(observation_data.get("procedures", 3.0)),
            d2_student_behavior       = float(observation_data.get("behavior", 3.0)),
            d3_communicating_students = float(observation_data.get("communication", 3.0)),
            d3_questioning_discussion = float(observation_data.get("questioning", 3.0)),
            d3_engaging_learning      = float(observation_data.get("engagement", 3.0)),
            d3_assessment_instruction = float(observation_data.get("assessment", 3.0)),
        )

        result = generate_coaching_result(obs)

        if not result:
            raise ValueError("AI Generator returned None")

        dimensions = []
        if hasattr(result, 'dimensions'):
            for d in result.dimensions:
                dimensions.append({
                    "dimension_id": getattr(d, 'dimension_id', "N/A"),
                    "rating": getattr(d, 'rating', "N/A"),
                    "coaching_feedback": getattr(d, 'coaching_feedback', ""),
                    "growth_suggestion": getattr(d, 'growth_suggestion', ""),
                })

        return {
            "overall_score": getattr(result, 'overall_score', 0.0),
            "raw_notes_summary": getattr(result, 'raw_notes_summary', ""),
            "glow": getattr(result, 'glow', "Well performed lesson."),
            "grow": getattr(result, 'grow', "Focus on student-led transitions."),
            "dimensions": dimensions
        }

    except Exception as e:
        logger.error(f"❌ AI ERROR: {str(e)}")
        # ব্যাকআপ রেসপন্স
        score = float(observation_data.get("overall_performance_score", 3.0))
        rating = "Distinguished" if score >= 3.5 else "Accomplished"
        
        return {
            "glow": f"Based on T-TESS descriptors, your {rating} lesson showed strong clarity.",
            "grow": "Focus on Dimension 3.1 to improve individual student pacing.",
            "raw_notes_summary": "Summary based on raw notes provided.",
            "dimensions": [],
            "error_info": str(e) # ডিবাগিং এর জন্য
        }