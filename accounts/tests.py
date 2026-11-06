from django.test import TestCase
from django.urls import reverse
from django.db import IntegrityError
from unittest.mock import patch
from accounts.models import User


class RegisterViewTests(TestCase):

    def setUp(self):
        self.register_url = reverse('register')
        self.home_url = reverse('home')
        self.valid_data = {
            'student_id': '2024001',
            'username': '测试用户',
            'password': 'test123456',
            'password_confirm': 'test123456',
        }

    def test_get_register_page_renders_form(self):
        """GET 请求应返回注册页面"""
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/register.html')
        self.assertContains(response, '注册')

    def test_register_success_creates_user(self):
        """正常注册：创建 User，is_verified=False，role='student'，自动登录并跳转首页"""
        response = self.client.post(self.register_url, self.valid_data, follow=True)
        self.assertRedirects(response, self.home_url)
        self.assertTrue(User.objects.filter(student_id='2024001').exists())
        user = User.objects.get(student_id='2024001')
        self.assertFalse(user.is_verified)
        self.assertEqual(user.role, 'student')
        # 验证密码已哈希
        self.assertNotEqual(user.password, 'test123456')
        self.assertTrue(user.check_password('test123456'))
        # 验证已登录
        self.assertIn('_auth_user_id', self.client.session)
        # 首页显示「待认证」
        self.assertContains(response, '待认证')

    def test_duplicate_student_id_rejected(self):
        """重复学号被拒绝"""
        User.objects.create_user(student_id='2024001', username='existing', password='pass123456')
        response = self.client.post(self.register_url, self.valid_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '该学号已被注册')
        self.assertEqual(User.objects.filter(student_id='2024001').count(), 1)

    def test_password_too_short_rejected(self):
        """密码少于6位被拒绝"""
        data = {**self.valid_data, 'password': '12345', 'password_confirm': '12345'}
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '密码长度不能少于 6 位')
        self.assertFalse(User.objects.filter(student_id='2024001').exists())

    def test_password_confirm_mismatch_rejected(self):
        """确认密码不一致被拒绝"""
        data = {**self.valid_data, 'password_confirm': 'different'}
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '两次输入的密码不一致')
        self.assertFalse(User.objects.filter(student_id='2024001').exists())

    def test_empty_student_id_rejected(self):
        """学号为空被拒绝"""
        data = {**self.valid_data, 'student_id': ''}
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '请输入学号')
        self.assertFalse(User.objects.filter(username='测试用户').exists())

    def test_empty_username_rejected(self):
        """昵称为空被拒绝"""
        data = {**self.valid_data, 'username': ''}
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '请输入昵称')
        self.assertFalse(User.objects.filter(student_id='2024001').exists())

    def test_authenticated_user_redirected(self):
        """已登录用户访问注册页重定向至首页"""
        User.objects.create_user(student_id='2024001', username='test', password='pass123456')
        self.client.login(username='2024001', password='pass123456')
        response = self.client.get(self.register_url)
        self.assertRedirects(response, self.home_url)

    def test_password_is_hashed_on_save(self):
        """验证密码以哈希形式存储（非明文）"""
        self.client.post(self.register_url, self.valid_data)
        user = User.objects.get(student_id='2024001')
        self.assertTrue(user.password.startswith('pbkdf2_sha256$'))

    def test_home_page_unauthenticated(self):
        """未登录用户访问首页应显示注册/登录入口"""
        response = self.client.get(self.home_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '请注册或登录')

    def test_admin_user_changelist(self):
        """管理员用户列表页应正常渲染"""
        User.objects.create_superuser(
            student_id='admin001', username='admin', password='adminpass123'
        )
        self.client.login(username='admin001', password='adminpass123')
        response = self.client.get(reverse('admin:accounts_user_changelist'))
        self.assertEqual(response.status_code, 200)

    def test_integrity_error_during_save_shows_student_id_error(self):
        """user.save() 抛出 IntegrityError（student_id 重复）时应返回表单错误"""
        with patch('accounts.models.User.save', side_effect=IntegrityError('student_id')):
            response = self.client.post(self.register_url, self.valid_data)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, '该学号已被注册')

    def test_integrity_error_during_save_shows_username_error(self):
        """user.save() 抛出 IntegrityError（username 重复）时应返回昵称相关错误"""
        with patch('accounts.models.User.save', side_effect=IntegrityError('username')):
            response = self.client.post(self.register_url, self.valid_data)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, '该昵称已被使用')

    def test_home_page_verified_user(self):
        """已认证用户访问首页应显示已通过认证"""
        user = User.objects.create_user(
            student_id='v001', username='verified_user', password='pass123456'
        )
        user.is_verified = True
        user.save()
        self.client.login(username='v001', password='pass123456')
        response = self.client.get(self.home_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '你的账号已通过认证')