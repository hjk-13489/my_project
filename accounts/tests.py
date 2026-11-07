from django.test import TestCase
from django.urls import reverse
from django.db import IntegrityError
from unittest.mock import patch
from accounts.models import User, VerificationRequest


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


class LoginViewTests(TestCase):

    def setUp(self):
        self.login_url = reverse('login')
        self.home_url = reverse('home')
        self.student_id = '2024002'
        self.password = 'testpass123'
        self.user = User.objects.create_user(
            student_id=self.student_id,
            username='登录测试用户',
            password=self.password,
        )

    def test_get_login_page_renders_form(self):
        """GET 请求应返回登录页面"""
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')
        self.assertContains(response, '登录')

    def test_login_success_redirects_home(self):
        """正常登录：建立 Session 并 302 跳转首页"""
        response = self.client.post(self.login_url, {
            'student_id': self.student_id,
            'password': self.password,
        })
        self.assertRedirects(response, self.home_url)
        self.assertIn('_auth_user_id', self.client.session)

    def test_login_success_with_next_parameter(self):
        """登录成功且带 ?next= 参数时跳转至指定页面"""
        response = self.client.post(
            self.login_url + '?next=/register/',
            {'student_id': self.student_id, 'password': self.password},
        )
        self.assertRedirects(response, '/register/', fetch_redirect_response=False)

    def test_login_external_next_redirects_home(self):
        """外部 ?next=http://evil.com 应忽略并跳转首页"""
        response = self.client.post(
            self.login_url + '?next=http://evil.com',
            {'student_id': self.student_id, 'password': self.password},
            follow=True,
        )
        self.assertRedirects(response, self.home_url)

    def test_login_empty_next_redirects_home(self):
        """空 ?next= 参数应回退跳转首页"""
        response = self.client.post(
            self.login_url + '?next=',
            {'student_id': self.student_id, 'password': self.password},
        )
        self.assertRedirects(response, self.home_url)

    def test_wrong_password_rejected(self):
        """错误密码：留在登录页并显示错误"""
        response = self.client.post(self.login_url, {
            'student_id': self.student_id,
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '学号或密码错误')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_nonexistent_student_id_rejected(self):
        """不存在的学号：留在登录页并显示错误（不区分学号不存在还是密码错误）"""
        response = self.client.post(self.login_url, {
            'student_id': '9999999',
            'password': self.password,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '学号或密码错误')

    def test_empty_student_id_rejected(self):
        """学号为空被拒绝"""
        response = self.client.post(self.login_url, {
            'student_id': '',
            'password': self.password,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '请输入学号')

    def test_empty_password_rejected(self):
        """密码为空被拒绝"""
        response = self.client.post(self.login_url, {
            'student_id': self.student_id,
            'password': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '请输入密码')

    def test_authenticated_user_redirected_from_login(self):
        """已登录用户访问登录页重定向至首页"""
        self.client.login(username=self.student_id, password=self.password)
        response = self.client.get(self.login_url)
        self.assertRedirects(response, self.home_url)


class LogoutViewTests(TestCase):

    def setUp(self):
        self.login_url = reverse('login')
        self.logout_url = reverse('logout')
        self.home_url = reverse('home')
        self.student_id = '2024003'
        self.password = 'logoutpass123'
        self.user = User.objects.create_user(
            student_id=self.student_id,
            username='登出测试用户',
            password=self.password,
        )

    def test_logout_clears_session_and_redirects_login(self):
        """登出：清除 Session 并 302 跳转 /login/"""
        self.client.login(username=self.student_id, password=self.password)
        self.assertIn('_auth_user_id', self.client.session)
        response = self.client.post(self.logout_url)
        self.assertRedirects(response, self.login_url)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_get_logout_returns_405(self):
        """GET /logout/ 应返回 405 Method Not Allowed"""
        self.client.login(username=self.student_id, password=self.password)
        response = self.client.get(self.logout_url)
        self.assertEqual(response.status_code, 405)

    def test_login_url_setting_configured_correctly(self):
        """配置验证：LOGIN_URL 设置正确"""
        from django.conf import settings
        self.assertEqual(settings.LOGIN_URL, '/login/')


class VerificationViewTests(TestCase):

    def setUp(self):
        self.verify_url = reverse('verify')
        self.home_url = reverse('home')
        self.student_id = '2024004'
        self.password = 'verifypass123'
        self.user = User.objects.create_user(
            student_id=self.student_id,
            username='认证测试用户',
            password=self.password,
        )

    def _login(self, student_id=None, password=None):
        self.client.login(
            username=student_id or self.student_id,
            password=password or self.password,
        )

    def _make_user(self, student_id, username='其他认证用户', password='otherpass123'):
        return User.objects.create_user(
            student_id=student_id, username=username, password=password
        )

    def test_get_verify_page_renders_form_with_prefilled_student_id(self):
        """GET 认证页：渲染表单并预填当前用户学号"""
        self._login()
        response = self.client.get(self.verify_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/verify.html')
        self.assertContains(response, '学号认证')
        self.assertContains(response, self.student_id)
        self.assertContains(response, '请输入真实姓名')

    def test_submit_creates_pending_request(self):
        """正常提交：创建 pending 申请，is_verified 仍为 False，显示成功提示"""
        self._login()
        response = self.client.post(self.verify_url, {
            'student_id': self.student_id,
            'name': '张三',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '认证申请已提交')
        request_obj = VerificationRequest.objects.get(user=self.user)
        self.assertEqual(request_obj.status, 'pending')
        self.assertEqual(request_obj.student_id, self.student_id)
        self.assertEqual(request_obj.name, '张三')
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_verified)

    def test_submit_ignores_tampered_student_id(self):
        """学号只读：POST 中篡改的学号被忽略，仍使用当前用户学号"""
        self._login()
        self.client.post(self.verify_url, {
            'student_id': '9999999',
            'name': '张三',
        })
        request_obj = VerificationRequest.objects.get(user=self.user)
        self.assertEqual(request_obj.student_id, self.student_id)

    def test_duplicate_pending_request_rejected(self):
        """已有 pending 申请时再次提交被拒绝"""
        VerificationRequest.objects.create(
            user=self.user, student_id=self.student_id, name='张三', status='pending'
        )
        self._login()
        response = self.client.post(self.verify_url, {
            'student_id': self.student_id,
            'name': '李四',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '你已有待审核的认证申请')
        self.assertEqual(VerificationRequest.objects.filter(user=self.user).count(), 1)
        self.assertEqual(VerificationRequest.objects.get(user=self.user).name, '张三')

    def test_get_verify_page_with_pending_request_shows_notice(self):
        """已有 pending 申请时访问认证页显示等待审核提示"""
        VerificationRequest.objects.create(
            user=self.user, student_id=self.student_id, name='张三', status='pending'
        )
        self._login()
        response = self.client.get(self.verify_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '认证申请已提交，等待管理员审核')

    def test_non_numeric_student_id_rejected(self):
        """学号含非数字字符被拒绝"""
        user = self._make_user('abc123')
        self._login('abc123', 'otherpass123')
        response = self.client.post(self.verify_url, {'name': '张三'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '学号格式不正确')
        self.assertFalse(VerificationRequest.objects.filter(user=user).exists())

    def test_too_short_student_id_rejected(self):
        """学号长度小于 4 位被拒绝"""
        user = self._make_user('123')
        self._login('123', 'otherpass123')
        response = self.client.post(self.verify_url, {'name': '张三'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '学号格式不正确')
        self.assertFalse(VerificationRequest.objects.filter(user=user).exists())

    def test_too_long_student_id_rejected(self):
        """学号长度大于 20 位被拒绝"""
        user = self._make_user('1' * 21)
        self._login('1' * 21, 'otherpass123')
        response = self.client.post(self.verify_url, {'name': '张三'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '学号格式不正确')
        self.assertFalse(VerificationRequest.objects.filter(user=user).exists())

    def test_empty_name_rejected(self):
        """姓名为空被拒绝"""
        self._login()
        response = self.client.post(self.verify_url, {'name': ''})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '请输入姓名')
        self.assertFalse(VerificationRequest.objects.filter(user=self.user).exists())

    def test_whitespace_only_name_rejected(self):
        """姓名仅含空白字符被拒绝"""
        self._login()
        response = self.client.post(self.verify_url, {'name': '   '})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '请输入姓名')
        self.assertFalse(VerificationRequest.objects.filter(user=self.user).exists())

    def test_unauthenticated_redirects_to_login(self):
        """未登录访问认证页：302 跳转登录页并携带 next"""
        response = self.client.get(self.verify_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            '/login/?next=/verify/',
        )

    def test_verified_user_redirected_home(self):
        """已认证用户访问认证页：302 重定向首页"""
        self.user.is_verified = True
        self.user.save(update_fields=['is_verified'])
        self._login()
        response = self.client.get(self.verify_url)
        self.assertRedirects(response, self.home_url)

    def test_verified_user_post_redirected_home(self):
        """已认证用户提交认证：302 重定向首页，不创建记录"""
        self.user.is_verified = True
        self.user.save(update_fields=['is_verified'])
        self._login()
        response = self.client.post(self.verify_url, {'name': '张三'})
        self.assertRedirects(response, self.home_url)
        self.assertFalse(VerificationRequest.objects.filter(user=self.user).exists())

    def test_rejected_request_can_be_resubmitted(self):
        """被驳回后重新提交：更新原记录为 pending，不创建新记录"""
        rejected = VerificationRequest.objects.create(
            user=self.user, student_id=self.student_id, name='旧姓名', status='rejected'
        )
        self._login()
        response = self.client.post(self.verify_url, {'name': '新姓名'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '认证申请已提交')
        self.assertEqual(VerificationRequest.objects.filter(user=self.user).count(), 1)
        rejected.refresh_from_db()
        self.assertEqual(rejected.status, 'pending')
        self.assertEqual(rejected.name, '新姓名')

    def test_rejected_request_get_renders_form(self):
        """被驳回后访问认证页可再次渲染表单"""
        VerificationRequest.objects.create(
            user=self.user, student_id=self.student_id, name='旧姓名', status='rejected'
        )
        self._login()
        response = self.client.get(self.verify_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '提交认证申请')

    def test_verified_badge_shown_in_navbar(self):
        """已认证用户任意页面导航栏显示「✓ 已认证」"""
        self.user.is_verified = True
        self.user.save(update_fields=['is_verified'])
        self._login()
        response = self.client.get(self.home_url)
        self.assertContains(response, '✓ 已认证')
        self.assertNotContains(response, '去认证')

    def test_pending_badge_and_entry_link_shown_in_navbar(self):
        """未认证用户导航栏显示「待认证」及认证入口链接"""
        self._login()
        response = self.client.get(self.home_url)
        self.assertContains(response, '待认证')
        self.assertContains(response, f'href="{self.verify_url}"')

    def test_home_page_unverified_shows_verify_entry(self):
        """首页未认证文案：你的账号尚未认证 + 认证入口"""
        self._login()
        response = self.client.get(self.home_url)
        self.assertContains(response, '你的账号尚未认证')
        self.assertContains(response, f'href="{self.verify_url}"')

    def test_admin_approve_action_syncs_is_verified(self):
        """管理员后台「通过认证」操作同步 User.is_verified=True"""
        verification = VerificationRequest.objects.create(
            user=self.user, student_id=self.student_id, name='张三', status='pending'
        )
        User.objects.create_superuser(
            student_id='admin001', username='admin', password='adminpass123'
        )
        self.client.login(username='admin001', password='adminpass123')
        response = self.client.post(
            reverse('admin:accounts_verificationrequest_changelist'),
            {
                'action': 'approve_requests',
                '_selected_action': [str(verification.pk)],
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        verification.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(verification.status, 'approved')
        self.assertTrue(self.user.is_verified)

    def test_admin_reject_action_keeps_user_unverified(self):
        """管理员后台「驳回」操作不改变 User.is_verified"""
        verification = VerificationRequest.objects.create(
            user=self.user, student_id=self.student_id, name='张三', status='pending'
        )
        User.objects.create_superuser(
            student_id='admin002', username='admin2', password='adminpass123'
        )
        self.client.login(username='admin002', password='adminpass123')
        response = self.client.post(
            reverse('admin:accounts_verificationrequest_changelist'),
            {
                'action': 'reject_requests',
                '_selected_action': [str(verification.pk)],
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        verification.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(verification.status, 'rejected')
        self.assertFalse(self.user.is_verified)


class ProfileViewTests(TestCase):

    def setUp(self):
        self.profile_url = reverse('profile')
        self.home_url = reverse('home')
        self.verify_url = reverse('verify')
        self.student_id = '2024005'
        self.username = '个人中心测试用户'
        self.password = 'profilepass123'
        self.user = User.objects.create_user(
            student_id=self.student_id,
            username=self.username,
            password=self.password,
        )

    def _login(self, student_id=None, password=None):
        self.client.login(
            username=student_id or self.student_id,
            password=password or self.password,
        )

    def _make_user(self, student_id, username='其他用户', password='otherpass123'):
        return User.objects.create_user(
            student_id=student_id, username=username, password=password
        )

    def test_unauthenticated_get_redirects_to_login_with_next(self):
        """未登录 GET /profile/：302 跳转登录页并携带 next=/profile/"""
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/login/?next=/profile/')

    def test_unauthenticated_post_redirects_to_login(self):
        """未登录 POST /profile/：@login_required 在外层，仍先 302 跳转登录页"""
        response = self.client.post(self.profile_url, {'foo': 'bar'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/login/?next=/profile/')

    def test_authenticated_get_returns_200_with_template(self):
        """已登录 GET /profile/：200 且渲染个人中心模板"""
        self._login()
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/profile.html')
        self.assertContains(response, '个人中心')

    def test_page_shows_only_own_nickname_and_student_id(self):
        """账号信息卡展示本人昵称、学号、认证状态徽标与注册时间"""
        self._login()
        response = self.client.get(self.profile_url)
        self.assertContains(response, '账号信息')
        self.assertContains(response, self.username)
        self.assertContains(response, self.student_id)
        self.assertContains(response, '认证状态')
        self.assertContains(response, '注册时间')
        # 徽标同时出现在导航栏与卡片，count=2 锁定卡片自身徽标
        self.assertContains(response, '待认证', count=2)
        self.assertContains(
            response, self.user.date_joined.strftime('%Y-%m-%d %H:%M')
        )

    def test_other_user_data_not_shown(self):
        """库中存在他人账号与认证申请时，页面不出现其昵称、学号、状态"""
        other = self._make_user('9998887', username='他人专属昵称ABC')
        VerificationRequest.objects.create(
            user=other, student_id='9998887', name='他人姓名', status='rejected'
        )
        self._login()
        response = self.client.get(self.profile_url)
        self.assertNotContains(response, '他人专属昵称ABC')
        self.assertNotContains(response, '9998887')
        self.assertNotContains(response, '他人姓名')
        self.assertNotContains(response, '已驳回')
        # 服务端 queryset 仅含本人数据（本人无申请）
        self.assertEqual(list(response.context['verification_requests']), [])
        self.assertContains(response, '尚未提交认证申请')

    def test_no_verification_request_shows_empty_state(self):
        """从未提交认证申请：显示中文空状态与去认证入口（按钮独有标记）"""
        self._login()
        response = self.client.get(self.profile_url)
        self.assertContains(response, '尚未提交认证申请')
        self.assertContains(response, '去认证')
        self.assertContains(response, f'href="{self.verify_url}"')
        # 导航栏同名链接不含此 class，此断言锁定卡片内按钮
        self.assertContains(response, 'btn btn-outline-primary btn-sm')

    def test_verification_history_shows_status_and_ordered(self):
        """有申请：显示 get_status_display() 与提交时间，按 -created_at 排序"""
        r1 = VerificationRequest.objects.create(
            user=self.user, student_id=self.student_id, name='张三', status='pending'
        )
        r2 = VerificationRequest.objects.create(
            user=self.user, student_id=self.student_id, name='张三', status='rejected'
        )
        r3 = VerificationRequest.objects.create(
            user=self.user, student_id=self.student_id, name='张三', status='approved'
        )
        from datetime import timedelta
        from django.utils import timezone
        now = timezone.now()
        times = [
            now - timedelta(days=3),
            now - timedelta(days=2),
            now - timedelta(days=1),
        ]
        for req, created_at in zip((r1, r2, r3), times):
            VerificationRequest.objects.filter(pk=req.pk).update(created_at=created_at)

        self._login()
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '待审核')
        self.assertContains(response, '已驳回')
        self.assertContains(response, '已通过')
        for created_at in times:
            self.assertContains(response, created_at.strftime('%Y-%m-%d %H:%M'))
        self.assertNotContains(response, '尚未提交认证申请')
        # 有认证历史时去认证按钮隐藏
        self.assertNotContains(response, 'btn btn-outline-primary btn-sm')
        self.assertEqual(
            [req.pk for req in response.context['verification_requests']],
            [r3.pk, r2.pk, r1.pk],
        )

    def test_four_sections_show_chinese_empty_state(self):
        """四个板块均呈现中文空状态提示"""
        self._login()
        response = self.client.get(self.profile_url)
        self.assertContains(response, '我的发布')
        self.assertContains(response, '我的订单')
        self.assertContains(response, '我的消息')
        self.assertContains(response, '我的评价')
        self.assertContains(response, '暂无发布记录')
        self.assertContains(response, '暂无订单记录')
        self.assertContains(response, '暂无消息记录')
        self.assertContains(response, '暂无评价记录')

    def test_authenticated_post_returns_405_without_writes(self):
        """已登录 POST /profile/：405，不写入任何数据"""
        self._login()
        response = self.client.post(self.profile_url, {'student_id': 'hacked'})
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response['Allow'], 'GET, HEAD')
        self.user.refresh_from_db()
        self.assertEqual(self.user.student_id, self.student_id)
        self.assertEqual(
            VerificationRequest.objects.filter(user=self.user).count(), 0
        )

    def test_http_method_restrictions(self):
        """已登录：PUT/PATCH/DELETE 405 且 Allow: GET, HEAD，HEAD 200"""
        self._login()
        for method in (self.client.put, self.client.patch, self.client.delete):
            response = method(self.profile_url)
            self.assertEqual(response.status_code, 405)
            self.assertEqual(response['Allow'], 'GET, HEAD')
        self.assertEqual(self.client.head(self.profile_url).status_code, 200)

    def test_navbar_profile_link_only_for_authenticated(self):
        """个人中心入口仅登录可见，且在渲染 base.html 的各页面均指向 /profile/"""
        anonymous = self.client.get(self.home_url)
        self.assertNotContains(anonymous, f'href="{self.profile_url}"')

        self._login()
        # 避开会 302 的注册/登录页，覆盖渲染 base.html 的页面
        for url in (self.home_url, self.verify_url, self.profile_url):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, msg=url)
            self.assertContains(response, f'href="{self.profile_url}"', msg_prefix=url)
            self.assertContains(response, '个人中心', msg_prefix=url)

    def test_verified_user_shows_verified_status(self):
        """已认证用户个人中心显示卡片自身的已认证徽标与注册信息"""
        self.user.is_verified = True
        self.user.save(update_fields=['is_verified'])
        self._login()
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        # 徽标同时出现在导航栏与卡片，count=2 锁定卡片自身徽标
        self.assertContains(response, '✓ 已认证', count=2)
        self.assertContains(response, '认证状态')
        self.assertContains(response, '注册时间')
        self.assertContains(
            response, self.user.date_joined.strftime('%Y-%m-%d %H:%M')
        )

    def test_go_verify_button_hidden_unverified_with_history(self):
        """未认证但已有申请：去认证按钮隐藏"""
        VerificationRequest.objects.create(
            user=self.user, student_id=self.student_id, name='张三', status='pending'
        )
        self._login()
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'btn btn-outline-primary btn-sm')

    def test_go_verify_button_hidden_verified_without_history(self):
        """已认证且无申请：去认证按钮隐藏"""
        self.user.is_verified = True
        self.user.save(update_fields=['is_verified'])
        self._login()
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'btn btn-outline-primary btn-sm')

    def test_mixed_history_isolates_other_user_data(self):
        """AD-4 混合场景：本人与他人都有申请时仅返回本人数据"""
        other = self._make_user('9998886', username='他人混合昵称XYZ')
        VerificationRequest.objects.create(
            user=other, student_id='9998886', name='他人混合姓名', status='rejected'
        )
        own = VerificationRequest.objects.create(
            user=self.user, student_id=self.student_id, name='本人姓名', status='pending'
        )
        self._login()
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [req.pk for req in response.context['verification_requests']],
            [own.pk],
        )
        self.assertNotContains(response, '他人混合昵称XYZ')
        self.assertNotContains(response, '9998886')
        self.assertNotContains(response, '他人混合姓名')
        self.assertNotContains(response, '已驳回')