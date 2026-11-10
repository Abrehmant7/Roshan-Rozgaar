from django.contrib import admin
from django.urls import include, path, re_path

from .views import api_not_found, spa_index

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("config.api_v1")),
    re_path(r"^api/", api_not_found),  # unknown API paths answer in JSON, never with the SPA
    # Built React app (frontend/dist) on the same origin; client-side routes fall through to it.
    re_path(r"^(?!api/|admin/|static/).*$", spa_index, name="spa"),
]
