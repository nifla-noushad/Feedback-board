from django.urls import path

from . import views

urlpatterns = [
    # Public
    path("", views.home, name="home"),
    path("submit/", views.submit, name="submit"),
    path("thank-you/", views.thank_you, name="thank_you"),
    path("my-feedback/", views.my_feedback, name="my_feedback"),
    path("my-feedback/<int:pk>/edit/", views.my_edit, name="my_edit"),
    path("my-feedback/<int:pk>/delete/", views.my_delete, name="my_delete"),
    # Admin
    path("admin-login/", views.AdminLoginView.as_view(), name="admin_login"),
    path("admin-logout/", views.admin_logout, name="admin_logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/export.csv", views.export_csv, name="export_csv"),
    path("dashboard/<int:pk>/edit/", views.edit, name="edit"),
    path("dashboard/<int:pk>/delete/", views.delete, name="delete"),
    path("dashboard/<int:pk>/status/", views.set_status, name="set_status"),
    # API
    path("api/feedback/", views.api_feedback, name="api_feedback"),
]
