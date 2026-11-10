from django.contrib import admin

from .models import ServiceArea, Specialty, Trade


class SpecialtyInline(admin.TabularInline):
    model = Specialty
    extra = 0
    fields = ["slug", "name_en", "name_ur", "sort_order", "is_active"]
    can_delete = False  # retire with is_active instead


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ["name_en", "name_ur", "slug", "icon_key", "sort_order", "is_active"]
    list_editable = ["sort_order", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name_en", "name_ur", "slug"]
    prepopulated_fields = {"slug": ["name_en"]}
    inlines = [SpecialtyInline]


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ["name_en", "name_ur", "trade", "slug", "sort_order", "is_active"]
    list_editable = ["sort_order", "is_active"]
    list_filter = ["trade", "is_active"]
    list_select_related = ["trade"]
    search_fields = ["name_en", "name_ur", "slug", "trade__name_en"]
    prepopulated_fields = {"slug": ["name_en"]}


@admin.register(ServiceArea)
class ServiceAreaAdmin(admin.ModelAdmin):
    list_display = ["sector_code", "city", "name_en", "name_ur", "sort_order", "is_active"]
    list_editable = ["sort_order", "is_active"]
    list_filter = ["city", "is_active"]
    search_fields = ["sector_code", "city", "name_en", "name_ur"]
