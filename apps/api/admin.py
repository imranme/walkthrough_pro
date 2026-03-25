from django.contrib import admin
from .models import Teacher, Observation

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display  = ("name", "school", "subject", "grade_level", "created_by", "created_at")
    list_filter   = ("school", "subject")
    search_fields = ("name", "school", "subject", "created_by__username")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Observation)
class ObservationAdmin(admin.ModelAdmin):
    list_display  = ("teacher", "created_by", "rating", "observation_date", "created_at")
    list_filter   = ("rating",)
    search_fields = ("teacher__name", "created_by__username")
    
    # Khub important: AI generated data gulo jeno admin bhuleo edit na kore, tai egulo readonly
    readonly_fields = ("ai_evidence", "glow", "grow", "domain_scores", "created_at", "updated_at")