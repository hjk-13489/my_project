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