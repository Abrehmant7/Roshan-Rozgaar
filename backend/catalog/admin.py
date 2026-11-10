from django import forms
from django.contrib import admin

from .models import ServiceArea, Specialty, Trade


class LowercaseSlugForm(forms.ModelForm):
    """Normalize the slug during field cleaning.

    Formset duplicate checks read `cleaned_data`, which Model.clean() never
    updates. Lowercasing here makes "Wall-Paint" and "wall-paint" in the same
    inline a form error instead of an IntegrityError (HTTP 500) on save.
    """

    def clean_slug(self):
        return self.cleaned_data["slug"].strip().lower()


class TradeForm(LowercaseSlugForm):
    class Meta:
        model = Trade
        fields = "__all__"


class SpecialtyForm(LowercaseSlugForm):
    class Meta:
        model = Specialty
        fields = "__all__"


class SpecialtyInline(admin.TabularInline):
    model = Specialty
    form = SpecialtyForm
    extra = 0
    fields = ["slug", "name_en", "name_ur", "sort_order", "is_active"]
    can_delete = False  # retire with is_active instead


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    form = TradeForm
    list_display = ["name_en", "name_ur", "slug", "icon_key", "sort_order", "is_active"]
    list_editable = ["sort_order", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name_en", "name_ur", "slug"]
    prepopulated_fields = {"slug": ["name_en"]}
    inlines = [SpecialtyInline]


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    form = SpecialtyForm
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
