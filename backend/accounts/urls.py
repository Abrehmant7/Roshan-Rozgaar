from django.urls import path

from . import views

app_name = "auth"

urlpatterns = [
    path("csrf/", views.csrf_token_view, name="csrf"),
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("me/", views.MeView.as_view(), name="me"),
]
