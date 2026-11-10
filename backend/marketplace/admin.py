from django.contrib import admin

from .models import JobRequest


@admin.register(JobRequest)
class JobRequestAdmin(admin.ModelAdmin):
    list_display = ["id", "customer", "trade", "service_area", "specialty", "status", "created_at"]
    list_filter = ["trade", "service_area"]
    list_select_related = ["customer", "trade", "service_area", "specialty"]
    search_fields = ["customer__username", "description"]
    readonly_fields = ["voice_note", "voice_note_type", "created_at", "updated_at"]
