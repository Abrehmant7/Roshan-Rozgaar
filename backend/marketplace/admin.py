from django.contrib import admin

from django.utils import timezone

from .models import Booking, JobRequest, Quote, Report, ReportStatus, Review


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


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["id", "booking", "worker", "customer", "rating", "created_at"]
    list_filter = ["rating"]
    list_select_related = ["booking", "worker", "customer"]
    readonly_fields = ["booking", "worker", "customer", "rating", "text", "tags", "created_at"]


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """Moderation queue: filter by status/reason, resolve or dismiss in bulk or one by one."""

    list_display = ["id", "created_at", "reason", "status", "reporter", "subject", "booking"]
    list_filter = ["status", "reason", "created_at"]
    list_select_related = ["reporter", "subject", "booking"]
    search_fields = ["reporter__username", "subject__username", "details"]
    readonly_fields = ["booking", "reporter", "subject", "reason", "details", "created_at", "resolved_by", "resolved_at"]
    fields = ["booking", "reporter", "subject", "reason", "details", "created_at",
              "status", "resolution_note", "resolved_by", "resolved_at"]
    actions = ["mark_resolved", "mark_dismissed"]

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        if "status" in form.changed_data:
            closed = obj.status != ReportStatus.OPEN
            obj.resolved_by = request.user if closed else None
            obj.resolved_at = timezone.now() if closed else None
        super().save_model(request, obj, form, change)

    def _close(self, request, queryset, new_status):
        n = queryset.filter(status=ReportStatus.OPEN).update(
            status=new_status, resolved_by=request.user, resolved_at=timezone.now())
        self.message_user(request, f"{n} report(s) marked {new_status.lower()}.")

    @admin.action(description="Mark selected reports resolved")
    def mark_resolved(self, request, queryset):
        self._close(request, queryset, ReportStatus.RESOLVED)

    @admin.action(description="Dismiss selected reports")
    def mark_dismissed(self, request, queryset):
        self._close(request, queryset, ReportStatus.DISMISSED)
