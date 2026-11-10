from django.contrib import admin

from .models import Booking, JobRequest, Quote


@admin.register(JobRequest)
class JobRequestAdmin(admin.ModelAdmin):
    list_display = ["id", "customer", "trade", "service_area", "specialty", "status", "created_at"]
    list_filter = ["trade", "service_area"]
    list_select_related = ["customer", "trade", "service_area", "specialty"]
    search_fields = ["customer__username", "description"]
    readonly_fields = ["voice_note", "voice_note_type", "created_at", "updated_at"]


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ["id", "job", "worker", "amount", "created_at"]
    list_select_related = ["job", "worker"]
    search_fields = ["worker__username"]


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    """Staff can correct a stuck booking's status here (e.g. after a no-show)."""

    list_display = ["id", "job", "customer", "worker", "amount", "status", "booked_at", "completed_at"]
    list_filter = ["status"]
    list_select_related = ["job", "customer", "worker"]
    search_fields = ["customer__username", "worker__username"]
    readonly_fields = ["job", "quote", "worker", "customer", "amount", "booked_at", "checked_in_at", "completed_at"]
