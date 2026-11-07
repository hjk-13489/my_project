from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, VerificationRequest


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


@admin.register(VerificationRequest)
class VerificationRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'student_id', 'name', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('student_id', 'name')
    list_select_related = ('user',)
    readonly_fields = ('created_at', 'updated_at')
    actions = ('approve_requests', 'reject_requests')

    @admin.action(description='通过认证（同步标记用户已认证）')
    def approve_requests(self, request, queryset):
        count = 0
        for verification in queryset.select_related('user'):
            verification.status = 'approved'
            verification.save(update_fields=['status', 'updated_at'])
            if not verification.user.is_verified:
                verification.user.is_verified = True
                verification.user.save(update_fields=['is_verified'])
            count += 1
        self.message_user(request, f'已通过 {count} 条认证申请。', messages.SUCCESS)

    @admin.action(description='驳回认证申请')
    def reject_requests(self, request, queryset):
        count = 0
        for verification in queryset:
            verification.status = 'rejected'
            verification.save(update_fields=['status', 'updated_at'])
            count += 1
        self.message_user(request, f'已驳回 {count} 条认证申请。', messages.WARNING)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # 在详情页将状态改为「已通过」时同样同步认证位
        if obj.status == 'approved' and not obj.user.is_verified:
            obj.user.is_verified = True
            obj.user.save(update_fields=['is_verified'])