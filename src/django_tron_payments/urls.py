"""Staff-only operational URLs for django-tron-payments."""

from django.urls import path

from django_tron_payments import views

app_name = "django_tron_payments"

urlpatterns = [
    path("", views.operations_dashboard, name="operations-dashboard"),
    path("run/<str:operation>/", views.run_operation, name="run-operation"),
]
