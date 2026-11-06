from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('student_id', 'username', 'email', 'is_verified', 'get_role_display', 'is_staff', 'is_active')
    list_filter = ('is_verified', 'role', 'is_staff', 'is_active')
    search_fields = ('student_id', 'username', 'email')
    ordering = ('student_id',)
    fieldsets = (
        (None, {'fields': ('student_id', 'username', 'password')}),
        ('认证信息', {'fields': ('is_verified', 'role')}),
        ('权限', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('日期', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('student_id', 'username', 'password1', 'password2', 'is_verified', 'role'),
        }),
    )