from django.contrib import admin

from .models import Feedback


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "message")
