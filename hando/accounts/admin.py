from django.contrib import admin

from accounts.models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "full_name",
        "job_title",
        "employee_code",
        "is_operational_active",
    ]
    search_fields = ["user__username", "full_name", "employee_code"]
