from django.contrib import admin

from .models import WorkerProfile


@admin.register(WorkerProfile)
class WorkerProfileAdmin(admin.ModelAdmin):
    list_display = ["display_name", "user", "experience_years", "accepting_jobs", "identity_simulated", "verified_at"]
    list_filter = ["accepting_jobs", "identity_simulated", "trades", "service_areas"]
    search_fields = ["display_name", "user__username", "verified_name"]
    filter_horizontal = ["trades", "specialties", "service_areas"]
    readonly_fields = ["verified_name", "id_masked", "identity_simulated", "verified_at", "created_at", "updated_at"]

    def has_add_permission(self, request):
        return False  # profiles are created through the ID-scan flow
