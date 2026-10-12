from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class IMSUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (('IMS', {'fields': ('role', 'phone', 'failed_attempts', 'locked_until')}),)
    list_display = ('username', 'email', 'role', 'is_active')
