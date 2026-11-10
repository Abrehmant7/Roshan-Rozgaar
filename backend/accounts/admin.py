from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User

_MARKETPLACE = ("Marketplace", {"fields": ("role",)})


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = (*DjangoUserAdmin.fieldsets, _MARKETPLACE)
    add_fieldsets = (*DjangoUserAdmin.add_fieldsets, _MARKETPLACE)
    list_display = (*DjangoUserAdmin.list_display, "role")
    list_filter = ("role", *DjangoUserAdmin.list_filter)
