from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    student_id = models.CharField(max_length=32, unique=True, verbose_name='学号')
    is_verified = models.BooleanField(default=False, verbose_name='是否已认证')
    role = models.CharField(
        max_length=16, choices=[('student', '学生'), ('admin', '管理员')],
        default='student', verbose_name='角色'
    )
    USERNAME_FIELD = 'student_id'
    REQUIRED_FIELDS = ['username']  # username 复用为昵称

    def __str__(self):
        return f"{self.student_id} ({self.username})"


class VerificationRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', '待审核'),
        ('approved', '已通过'),
        ('rejected', '已驳回'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='verification_requests',
        verbose_name='用户'
    )
    student_id = models.CharField(max_length=32, verbose_name='学号')
    name = models.CharField(max_length=30, verbose_name='姓名')
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default='pending', verbose_name='状态'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='提交时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '认证申请'
        verbose_name_plural = '认证申请'
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(status='pending'),
                name='unique_pending_verification_per_user',
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.student_id}) - {self.get_status_display()}"