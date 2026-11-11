import importlib
import os
import shutil
import tempfile
from decimal import Decimal
from io import BytesIO

import config.urls
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import clear_url_caches, reverse
from PIL import Image

from accounts.models import User
from listings.models import InvalidTransition, Product, ProductImage

# 以临时目录隔离 media/，避免上传测试污染真实 media/ 与既有数据。
_TEST_MEDIA_ROOT = tempfile.mkdtemp()


def _make_image(fmt='JPEG', name='photo.jpg'):
    """用 Pillow 生成内存中的真实图片，供上传测试使用。"""
    buffer = BytesIO()
    Image.new('RGB', (8, 8), (200, 30, 30)).save(buffer, format=fmt)
    content_type = 'image/jpeg' if fmt == 'JPEG' else 'image/png'
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)


@override_settings(MEDIA_ROOT=_TEST_MEDIA_ROOT)
class PublishViewTests(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        # 每个用例都从空 media/ 起步，保证「不写文件」断言不被上一用例残留干扰。
        shutil.rmtree(_TEST_MEDIA_ROOT, ignore_errors=True)
        os.makedirs(_TEST_MEDIA_ROOT, exist_ok=True)

        self.url = reverse('publish')
        self.user = User.objects.create_user(
            student_id='2024001', username='卖家', password='test123456'
        )
        self.other_user = User.objects.create_user(
            student_id='2024002', username='其他用户', password='test123456'
        )
        self.valid_data = {
            'title': '高等数学教材',
            'description': '九成新，无笔记',
            'price': '25.00',
            'condition': '良好',
            'category': '教材',
        }

    # ---------- helpers ----------
    def _login_verified(self):
        self.user.is_verified = True
        self.user.save()
        self.client.login(username='2024001', password='test123456')

    def _login_unverified(self):
        self.client.login(username='2024001', password='test123456')

    def _post(self, data=None, images=None):
        payload = dict(self.valid_data if data is None else data)
        payload['images'] = images if images is not None else [_make_image()]
        return self.client.post(self.url, payload)

    def _media_files(self):
        found = []
        for root, _, names in os.walk(_TEST_MEDIA_ROOT):
            for name in names:
                found.append(os.path.join(root, name))
        return found

    def _assert_no_writes(self):
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(ProductImage.objects.count(), 0)
        self.assertEqual(self._media_files(), [])

    # ---------- GET / 合法提交 ----------
    def test_verified_get_renders_multipart_form(self):
        self._login_verified()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'listings/publish.html')
        self.assertContains(response, 'enctype="multipart/form-data"', count=1)
        self.assertContains(
            response, '商品图片（1–5 张，仅 JPEG/PNG，单张不超过 5MB）', count=1
        )
        self.assertContains(response, '提交发布', count=1)
        self._assert_no_writes()

    def test_logged_in_nav_exposes_publish_link(self):
        """删除 base.html 的「发布商品」入口后，首页将不再出现该链接，本用例应失败。"""
        self._login_verified()
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="%s"' % reverse('publish'), count=1)
        self.assertContains(response, '发布商品', count=1)

    def test_valid_submission_creates_pending_product_and_one_image(self):
        self._login_verified()
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '已提交，等待管理员审核', count=1)
        self.assertEqual(Product.objects.count(), 1)
        product = Product.objects.first()
        self.assertEqual(product.owner, self.user)
        self.assertEqual(product.status, 'pending')
        self.assertEqual(product.title, '高等数学教材')
        self.assertEqual(product.price, Decimal('25.00'))
        self.assertEqual(ProductImage.objects.count(), 1)
        self.assertEqual(product.images.count(), 1)
        files = self._media_files()
        self.assertEqual(len(files), 1)
        self.assertEqual(os.path.dirname(files[0]), os.path.join(_TEST_MEDIA_ROOT, 'products'))

    def test_five_images_boundary_is_accepted(self):
        self._login_verified()
        images = [_make_image(name=f'p{i}.jpg') for i in range(5)]
        response = self._post(images=images)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '已提交，等待管理员审核', count=1)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(ProductImage.objects.count(), 5)
        self.assertEqual(len(self._media_files()), 5)

    def test_owner_and_status_forced_ignoring_posted_values(self):
        """owner/status 恒为 request.user / pending，不接受表单或请求传值。"""
        self._login_verified()
        data = dict(self.valid_data)
        data['owner'] = self.other_user.pk
        data['status'] = 'approved'
        response = self._post(data=data)
        self.assertEqual(response.status_code, 200)
        product = Product.objects.first()
        self.assertEqual(product.owner, self.user)
        self.assertEqual(product.status, 'pending')

    # ---------- 字段 / 价格 / 枚举 ----------
    def test_missing_required_fields_show_chinese_errors(self):
        self._login_verified()
        expected = {
            'title': '请输入商品标题',
            'description': '请输入商品描述',
            'price': '请输入价格',
            'condition': '请选择成色',
            'category': '请选择分类',
        }
        for field, message in expected.items():
            with self.subTest(field=field):
                data = dict(self.valid_data)
                del data[field]
                response = self._post(data=data)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, message, count=1)
                self._assert_no_writes()

    def test_price_non_numeric_rejected(self):
        self._login_verified()
        response = self._post(data={**self.valid_data, 'price': 'abc'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '请输入有效的价格数字', count=1)
        self._assert_no_writes()

    def test_price_zero_rejected(self):
        self._login_verified()
        response = self._post(data={**self.valid_data, 'price': '0'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '价格必须大于 0', count=1)
        self._assert_no_writes()

    def test_price_negative_rejected(self):
        self._login_verified()
        response = self._post(data={**self.valid_data, 'price': '-1'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '价格必须大于 0', count=1)
        self._assert_no_writes()

    def test_category_out_of_range_rejected(self):
        self._login_verified()
        response = self._post(data={**self.valid_data, 'category': '非法分类'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '请选择有效的分类', count=1)
        self._assert_no_writes()

    def test_condition_out_of_range_rejected(self):
        self._login_verified()
        response = self._post(data={**self.valid_data, 'condition': '未知'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '请选择有效的成色', count=1)
        self._assert_no_writes()

    def test_all_valid_category_and_condition_choices_are_accepted(self):
        """合法枚举不能只覆盖 教材/良好，全部取值都要有回归证据。"""
        self._login_verified()
        for category, _ in Product.CATEGORY_CHOICES:
            for condition, _ in Product.CONDITION_CHOICES:
                with self.subTest(category=category, condition=condition):
                    # 每个组合独立计数，清空上一组合的 DB 与 media/ 残留。
                    Product.objects.all().delete()
                    shutil.rmtree(_TEST_MEDIA_ROOT, ignore_errors=True)
                    os.makedirs(_TEST_MEDIA_ROOT, exist_ok=True)
                    response = self._post(data={
                        **self.valid_data, 'category': category, 'condition': condition,
                    })
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, '已提交，等待管理员审核', count=1)
                    self.assertEqual(Product.objects.count(), 1)

    def test_form_error_messages_boundary_cases(self):
        """title.max_length 与 price 三个精度上限的中文文案都要有边界断言。"""
        self._login_verified()
        cases = [
            ({'title': '标' * 101}, '商品标题不能超过 100 个字符'),
            ({'price': '1.234'}, '价格最多保留 2 位小数'),
            ({'price': '12345678901.00'}, '价格数字位数过长'),
            ({'price': '123456789.0'}, '价格整数部分过长'),
        ]
        for override, message in cases:
            with self.subTest(override=override):
                response = self._post(data={**self.valid_data, **override})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, message, count=1)
                self._assert_no_writes()

    # ---------- 图片 ----------
    def test_no_image_rejected(self):
        self._login_verified()
        response = self._post(images=[])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '请至少上传 1 张商品图片', count=1)
        self._assert_no_writes()

    def test_six_images_rejected(self):
        self._login_verified()
        images = [_make_image(name=f'p{i}.jpg') for i in range(6)]
        response = self._post(images=images)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '最多只能上传 5 张商品图片', count=1)
        self._assert_no_writes()

    def test_gif_disguised_as_jpg_rejected(self):
        """真实格式为 GIF（扩展名伪装成 .jpg）→ 按 img.format 拒绝。"""
        self._login_verified()
        response = self._post(images=[_make_image(fmt='GIF', name='fake.jpg')])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '仅支持 JPEG/PNG 格式的图片', count=1)
        self._assert_no_writes()

    def test_non_image_disguised_as_png_rejected(self):
        self._login_verified()
        fake = SimpleUploadedFile('fake.png', b'this is not an image', content_type='image/png')
        response = self._post(images=[fake])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '图片文件损坏或格式不支持，仅支持 JPEG/PNG', count=1)
        self._assert_no_writes()

    def test_oversized_image_rejected(self):
        self._login_verified()
        big = SimpleUploadedFile(
            'big.png', b'x' * (5 * 1024 * 1024 + 1), content_type='image/png'
        )
        response = self._post(images=[big])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '单张图片不能超过 5MB', count=1)
        self._assert_no_writes()

    def test_mixed_valid_and_invalid_images_write_nothing(self):
        """一张合法 + 一张非法：无部分落库、无文件落盘。"""
        self._login_verified()
        response = self._post(images=[_make_image(), _make_image(fmt='GIF', name='fake.jpg')])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '仅支持 JPEG/PNG 格式的图片', count=1)
        self._assert_no_writes()

    def test_valid_png_submission_is_accepted(self):
        """PNG 合法路径必须真正执行（把允许格式缩成只 JPEG 时本用例应失败）。"""
        self._login_verified()
        response = self._post(images=[_make_image(fmt='PNG', name='photo.png')])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '已提交，等待管理员审核', count=1)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(ProductImage.objects.count(), 1)
        self.assertEqual(len(self._media_files()), 1)

    def test_real_jpeg_with_png_extension_is_accepted(self):
        """按 img.format 判定而非扩展名：真实 JPEG 内容叫 .png 也应通过。"""
        self._login_verified()
        jpeg = _make_image(fmt='JPEG')
        jpeg.seek(0)
        disguised = SimpleUploadedFile(
            'looks-like-png.png', jpeg.read(), content_type='image/png'
        )
        response = self._post(images=[disguised])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '已提交，等待管理员审核', count=1)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(ProductImage.objects.count(), 1)
        self.assertEqual(len(self._media_files()), 1)

    def test_uploaded_image_is_served_via_debug_media_route(self):
        """删除 config/urls.py 的 DEBUG static() 后 /media/... 会 404，本用例应失败。"""
        self._login_verified()
        jpeg = _make_image()
        jpeg.seek(0)
        expected_bytes = jpeg.read()
        jpeg.seek(0)
        self._post(images=[jpeg])
        image_url = ProductImage.objects.get().image.url

        # 在 DEBUG=True 下重新执行 config/urls.py，确定性复现「DEBUG 挂 static()」分支；
        # 该分支被删时重载后的 urlpatterns 不含媒体路由，GET 将返回 404。
        original_urlpatterns = config.urls.urlpatterns
        try:
            with override_settings(DEBUG=True):
                importlib.reload(config.urls)
                clear_url_caches()
                served = self.client.get(image_url)
                self.assertEqual(served.status_code, 200)
                self.assertEqual(b''.join(served.streaming_content), expected_bytes)
        finally:
            # 还原全局 URLconf 状态，避免污染同一进程内后续用例。
            config.urls.urlpatterns = original_urlpatterns
            clear_url_caches()

    # ---------- 门控 ----------
    def test_unverified_get_shows_verification_prompt(self):
        self._login_unverified()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'listings/publish.html')
        self.assertContains(response, '需先完成学号认证', count=1)
        # 导航栏「去认证」+ 提示页「去认证」共两处
        self.assertContains(response, '去认证', count=2)
        self.assertContains(response, 'class="btn btn-warning">去认证', count=1)
        self._assert_no_writes()

    def test_unverified_post_creates_nothing(self):
        self._login_unverified()
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '需先完成学号认证', count=1)
        self._assert_no_writes()

    def test_unauthenticated_get_redirects_to_login_with_next(self):
        response = self.client.get(self.url)
        self.assertRedirects(
            response, '/login/?next=/listings/publish/', fetch_redirect_response=False
        )
        self._assert_no_writes()

    def test_unauthenticated_post_redirects_to_login_with_next(self):
        response = self._post()
        self.assertRedirects(
            response, '/login/?next=/listings/publish/', fetch_redirect_response=False
        )
        self._assert_no_writes()

    def test_unsafe_methods_return_405(self):
        self._login_verified()
        for method in ('put', 'patch', 'delete'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.url)
                self.assertEqual(response.status_code, 405)
        self._assert_no_writes()

    def test_head_allowed_and_writes_nothing(self):
        self._login_verified()
        response = self.client.head(self.url)
        self.assertEqual(response.status_code, 200)
        self._assert_no_writes()


@override_settings(MEDIA_ROOT=_TEST_MEDIA_ROOT)
class ProductVisibilityTests(TestCase):
    """Story 2.2：visible() 唯一门控与模型层状态流转的回归证据（不改既有 28 例）。"""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user(
            student_id='2024101', username='卖家', password='test123456'
        )
        shutil.rmtree(_TEST_MEDIA_ROOT, ignore_errors=True)
        os.makedirs(_TEST_MEDIA_ROOT, exist_ok=True)

    def _create_product(self, status='pending', **kwargs):
        data = {
            'owner': self.user,
            'title': '高等数学教材',
            'description': '九成新，无笔记',
            'price': Decimal('25.00'),
            'condition': '良好',
            'category': '教材',
            'status': status,
        }
        data.update(kwargs)
        return Product.objects.create(**data)

    # ---------- 四态可见性 ----------
    def test_pending_not_visible_but_in_base_queryset(self):
        product = self._create_product(status='pending')
        self.assertEqual(Product.objects.visible().filter(id=product.id).count(), 0)
        self.assertEqual(Product.objects.count(), 1)  # 基础查询集本身不过滤

    def test_visible_returns_only_approved(self):
        self._create_product(status='pending')
        approved = self._create_product(status='approved')
        self._create_product(status='rejected')
        self._create_product(status='offline')
        self.assertEqual(Product.objects.count(), 4)
        self.assertEqual(list(Product.objects.visible()), [approved])

    def test_offline_not_visible(self):
        product = self._create_product(status='offline')
        self.assertEqual(Product.objects.visible().filter(id=product.id).count(), 0)

    # ---------- 合法转移：状态变更持久化，visible() 即刻命中 ----------
    def test_approve_persists_and_becomes_visible(self):
        product = self._create_product(status='pending')
        product.approve()
        self.assertEqual(product.status, 'approved')
        product.refresh_from_db()
        self.assertEqual(product.status, 'approved')
        self.assertEqual(Product.objects.visible().filter(id=product.id).count(), 1)

    def test_reject_persists_and_stays_invisible(self):
        product = self._create_product(status='pending')
        product.reject()
        self.assertEqual(product.status, 'rejected')
        product.refresh_from_db()
        self.assertEqual(product.status, 'rejected')
        self.assertEqual(Product.objects.visible().filter(id=product.id).count(), 0)

    def test_status_change_needs_no_query_code_change(self):
        """同一商品 pending → approved 后 visible() 自动命中，无需改任何查询代码。"""
        product = self._create_product(status='pending')
        self.assertEqual(Product.objects.visible().filter(id=product.id).count(), 0)
        product.approve()
        self.assertEqual(Product.objects.visible().filter(id=product.id).count(), 1)

    # ---------- 非法转移：显式拒绝、保持原状态、不落库 ----------
    def test_approve_from_non_pending_raises_and_no_write(self):
        for status in ('approved', 'rejected', 'offline'):
            with self.subTest(status=status):
                product = self._create_product(status=status)
                product.refresh_from_db()
                original_updated_at = product.updated_at
                with self.assertRaises(InvalidTransition):
                    product.approve()
                self.assertEqual(product.status, status)  # 内存状态未改
                product.refresh_from_db()
                self.assertEqual(product.status, status)  # DB 状态未改
                self.assertEqual(product.updated_at, original_updated_at)  # 未落库

    def test_reject_from_non_pending_raises(self):
        for status in ('approved', 'rejected', 'offline'):
            with self.subTest(status=status):
                product = self._create_product(status=status)
                with self.assertRaises(InvalidTransition):
                    product.reject()
                self.assertEqual(product.status, status)
                product.refresh_from_db()
                self.assertEqual(product.status, status)

    def test_transition_to_undefined_target_raises_and_no_write(self):
        """pending → offline 等未定义目标态统一走 InvalidTransition（含中文异常）。"""
        product = self._create_product(status='pending')
        product.refresh_from_db()
        original_updated_at = product.updated_at
        with self.assertRaises(InvalidTransition) as ctx:
            product._transition('offline')
        self.assertIn('非法状态流转', str(ctx.exception))
        self.assertIn('待审核', str(ctx.exception))
        self.assertEqual(product.status, 'pending')
        product.refresh_from_db()
        self.assertEqual(product.status, 'pending')
        self.assertEqual(product.updated_at, original_updated_at)

    def test_illegal_transition_message_is_chinese(self):
        product = self._create_product(status='approved')
        with self.assertRaises(InvalidTransition) as ctx:
            product.approve()
        self.assertIn('非法状态流转', str(ctx.exception))
        self.assertIn('已上架', str(ctx.exception))

    # ---------- 链式组合 ----------
    def test_visible_chains_with_filter(self):
        approved_textbook = self._create_product(status='approved', category='教材')
        self._create_product(status='approved', category='日用品')
        self._create_product(status='pending', category='教材')
        result = Product.objects.visible().filter(category='教材')
        self.assertEqual(list(result), [approved_textbook])
        self.assertEqual(result.count(), 1)
        # visible() 挂在自定义 QuerySet 上，filter() 之后仍可调用
        self.assertEqual(Product.objects.filter(category='教材').visible().count(), 1)

    # ---------- 发布回归 ----------
    def test_publish_regression_still_pending_and_invisible(self):
        self.user.is_verified = True
        self.user.save()
        self.client.login(username='2024101', password='test123456')
        response = self.client.post(
            reverse('publish'),
            {
                'title': '高等数学教材',
                'description': '九成新，无笔记',
                'price': '25.00',
                'condition': '良好',
                'category': '教材',
                'images': [_make_image()],
            },
        )
        self.assertEqual(response.status_code, 200)
        product = Product.objects.get()
        self.assertEqual(product.status, 'pending')
        self.assertEqual(Product.objects.visible().filter(id=product.id).count(), 0)


# ---------------------------------------------------------------------------
# Story 2.3：驳回通知与重新提交。本段自包含追加，不改动上方既有测试类。
# ---------------------------------------------------------------------------
import tempfile
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image as PILImage

from .models import InvalidTransition, Product, ProductImage, RejectionNotice

_STORY23_MEDIA_ROOT = tempfile.mkdtemp(prefix='story23-media-')


def _story23_image(name='pic.png', fmt='PNG'):
    """生成一张 Pillow 可 verify() 的真实 JPEG/PNG 内存图片。"""
    buf = BytesIO()
    PILImage.new('RGB', (8, 8)).save(buf, format=fmt)
    content_type = 'image/jpeg' if fmt == 'JPEG' else 'image/png'
    return SimpleUploadedFile(name, buf.getvalue(), content_type=content_type)


@override_settings(MEDIA_ROOT=_STORY23_MEDIA_ROOT)
class RejectionNoticeAndResubmitTests(TestCase):
    """覆盖 spec-2-3 I/O 矩阵：通知可见性/越权/持久化、重提各分支、非法路径、再审核。"""

    def setUp(self):
        self.User = get_user_model()
        self.owner = self.User.objects.create_user(
            student_id='20232301', username='卖家甲', password='testpass12345'
        )
        self.other = self.User.objects.create_user(
            student_id='20232302', username='卖家乙', password='testpass12345'
        )
        for user in (self.owner, self.other):
            user.is_verified = True
            user.save(update_fields=['is_verified'])
        self.valid_data = {
            'title': '重新提交后的标题',
            'description': '重新提交后的描述',
            'price': '30.00',
            'condition': '良好',
            'category': '教材',
        }

    def _make_product(self, owner=None, status='pending'):
        return Product.objects.create(
            owner=owner or self.owner,
            title='原商品标题',
            description='原商品描述',
            price=Decimal('25.00'),
            condition='中等',
            category='教材',
            status=status,
        )

    def _reject_with_reason(self, product, reason='图片不清晰，请重新上传'):
        product.reject(reason)
        return product

    def _attach_images(self, product, count=2, prefix='old'):
        for i in range(count):
            ProductImage.objects.create(
                product=product, image=_story23_image(f'{prefix}_{i}.png')
            )

    def _login(self, user=None):
        self.client.force_login(user or self.owner)

    # ---- 通知可见性与越权隔离 ----
    def test_notice_visible_only_to_owner(self):
        product = self._make_product()
        self._reject_with_reason(product, '独家理由-甲-12345')
        self._login()
        resp = self.client.get(reverse('profile'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '原商品标题')
        self.assertContains(resp, '独家理由-甲-12345')
        self.assertContains(resp, '已驳回')

        self.client.force_login(self.other)
        resp_other = self.client.get(reverse('profile'))
        self.assertNotContains(resp_other, '原商品标题')
        self.assertNotContains(resp_other, '独家理由-甲-12345')
        self.assertContains(resp_other, '暂无消息记录，你还没有任何消息')

    def test_reject_creates_owner_scoped_notice(self):
        product = self._make_product()
        product.reject('第一次驳回理由')
        notice = RejectionNotice.objects.get(product=product)
        self.assertEqual(notice.owner_id, self.owner.pk)
        self.assertEqual(notice.reason, '第一次驳回理由')
        self.assertEqual(RejectionNotice.objects.filter(owner=self.other).count(), 0)

    def test_messages_empty_state(self):
        self._login()
        resp = self.client.get(reverse('profile'))
        self.assertTrue(resp.context['my_messages_empty'])
        self.assertContains(resp, '暂无消息记录，你还没有任何消息')

    def test_cross_user_resubmit_returns_404(self):
        product = self._make_product()
        self._reject_with_reason(product, '甲的理由-不可见')
        self.client.force_login(self.other)
        url = reverse('resubmit', args=[product.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, self.valid_data).status_code, 404)
        self.assertNotContains(self.client.get(reverse('profile')), '甲的理由-不可见')
        product.refresh_from_db()
        self.assertEqual(product.status, 'rejected')
        self.assertEqual(product.title, '原商品标题')

    def test_login_required_for_messages_and_resubmit(self):
        product = self._make_product()
        self._reject_with_reason(product)
        for url in (reverse('profile'), reverse('resubmit', args=[product.pk])):
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 302)
                self.assertIn('/login/', resp['Location'])
                self.assertIn('next=', resp['Location'])

    def test_unverified_user_gets_prompt_page(self):
        product = self._make_product()
        self._reject_with_reason(product)
        self.owner.is_verified = False
        self.owner.save(update_fields=['is_verified'])
        self._login()
        resp = self.client.get(reverse('resubmit', args=[product.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '需先完成学号认证')
        product.refresh_from_db()
        self.assertEqual(product.status, 'rejected')

    # ---- 重提成功与持久化 ----
    def test_resubmit_get_shows_reason_and_original_images(self):
        product = self._make_product()
        self._attach_images(product, count=2)
        self._reject_with_reason(product, '页面上应显示的驳回理由')
        self._login()
        resp = self.client.get(reverse('resubmit', args=[product.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '页面上应显示的驳回理由')
        self.assertContains(resp, '原商品标题')
        self.assertContains(resp, '2 张图片')

    def test_resubmit_without_images_keeps_originals_and_updates_fields(self):
        product = self._make_product()
        self._attach_images(product, count=2)
        self._reject_with_reason(product)
        original_pk = product.pk
        original_owner_id = product.owner_id
        original_created_at = product.created_at
        self._login()
        resp = self.client.post(reverse('resubmit', args=[product.pk]), self.valid_data)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '已重新提交')
        product.refresh_from_db()
        self.assertEqual(product.pk, original_pk)
        self.assertEqual(product.owner_id, original_owner_id)
        self.assertEqual(product.created_at, original_created_at)
        self.assertEqual(product.title, '重新提交后的标题')
        self.assertEqual(product.description, '重新提交后的描述')
        self.assertEqual(product.price, Decimal('30.00'))
        self.assertEqual(product.condition, '良好')
        self.assertEqual(product.category, '教材')
        self.assertEqual(product.status, 'pending')
        self.assertEqual(product.images.count(), 2)
        self.assertEqual(Product.objects.visible().filter(pk=product.pk).count(), 0)

    def test_resubmit_with_images_replaces_in_one_transaction(self):
        product = self._make_product()
        self._attach_images(product, count=3, prefix='seed')
        self._reject_with_reason(product)
        old_names = list(product.images.values_list('image', flat=True))
        self._login()
        new_images = [_story23_image(f'fresh_{i}.png') for i in range(2)]
        resp = self.client.post(
            reverse('resubmit', args=[product.pk]),
            dict(self.valid_data, images=new_images),
        )
        self.assertEqual(resp.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.status, 'pending')
        self.assertEqual(product.title, '重新提交后的标题')
        self.assertEqual(product.images.count(), 2)
        new_names = list(product.images.values_list('image', flat=True))
        self.assertEqual(len(new_names), 2)
        self.assertFalse(set(new_names) & set(old_names))

    def test_status_cannot_be_set_by_request(self):
        product = self._make_product()
        self._attach_images(product, count=1, prefix='nostatus')
        self._reject_with_reason(product)
        self._login()
        resp = self.client.post(
            reverse('resubmit', args=[product.pk]),
            dict(self.valid_data, status='approved'),
        )
        self.assertEqual(resp.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.status, 'pending')
        self.assertEqual(Product.objects.visible().filter(pk=product.pk).count(), 0)

    def test_reason_persists_after_resubmit(self):
        product = self._make_product()
        self._attach_images(product, count=1, prefix='persist')
        self._reject_with_reason(product, '重提后仍应可见的理由')
        self._login()
        self.client.post(reverse('resubmit', args=[product.pk]), self.valid_data)
        product.refresh_from_db()
        self.assertEqual(product.status, 'pending')
        self.assertEqual(RejectionNotice.objects.filter(product=product).count(), 1)
        resp = self.client.get(reverse('profile'))
        self.assertContains(resp, '重提后仍应可见的理由')
        self.assertContains(resp, '待审核')

    # ---- 校验失败不落库 ----
    def test_form_validation_failure_writes_nothing(self):
        product = self._make_product()
        self._attach_images(product, count=1, prefix='keep')
        self._reject_with_reason(product)
        notices_before = RejectionNotice.objects.count()
        self._login()
        resp = self.client.post(
            reverse('resubmit', args=[product.pk]), dict(self.valid_data, price='0')
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '价格必须大于 0')
        product.refresh_from_db()
        self.assertEqual(product.status, 'rejected')
        self.assertEqual(product.title, '原商品标题')
        self.assertEqual(product.images.count(), 1)
        self.assertEqual(RejectionNotice.objects.count(), notices_before)

    def test_image_validation_failure_writes_nothing(self):
        product = self._make_product()
        self._attach_images(product, count=2, prefix='keep')
        self._reject_with_reason(product)
        self._login()
        broken = SimpleUploadedFile('fake.gif', b'not a real image', content_type='image/gif')
        resp = self.client.post(
            reverse('resubmit', args=[product.pk]), dict(self.valid_data, images=[broken])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '图片文件损坏或格式不支持，仅支持 JPEG/PNG')
        product.refresh_from_db()
        self.assertEqual(product.status, 'rejected')
        self.assertEqual(product.title, '原商品标题')
        self.assertEqual(product.images.count(), 2)

    # ---- 非法路径 ----
    def test_non_rejected_states_return_404(self):
        self._login()
        for status in ('pending', 'approved', 'offline'):
            with self.subTest(status=status):
                product = self._make_product(status=status)
                url = reverse('resubmit', args=[product.pk])
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url, self.valid_data).status_code, 404)
                product.refresh_from_db()
                self.assertEqual(product.status, status)
                self.assertEqual(product.title, '原商品标题')

    def test_illegal_resubmit_raises_and_creates_no_notice(self):
        product = self._make_product(status='approved')
        before = RejectionNotice.objects.count()
        with self.assertRaises(InvalidTransition):
            product.resubmit()
        product.refresh_from_db()
        self.assertEqual(product.status, 'approved')
        self.assertEqual(RejectionNotice.objects.count(), before)

    def test_illegal_reject_creates_no_notice(self):
        product = self._make_product(status='approved')
        before = RejectionNotice.objects.count()
        with self.assertRaises(InvalidTransition):
            product.reject('不该留下的理由')
        product.refresh_from_db()
        self.assertEqual(product.status, 'approved')
        self.assertEqual(RejectionNotice.objects.count(), before)

    # ---- 重提后再审核 ----
    def test_resubmit_then_approve_matches_story_22(self):
        product = self._make_product()
        product.reject('理由')
        product.resubmit()
        product.refresh_from_db()
        self.assertEqual(product.status, 'pending')
        self.assertEqual(Product.objects.visible().filter(pk=product.pk).count(), 0)
        product.approve()
        product.refresh_from_db()
        self.assertEqual(product.status, 'approved')
        self.assertEqual(Product.objects.visible().filter(pk=product.pk).count(), 1)

    def test_resubmit_then_reject_creates_new_notice(self):
        product = self._make_product()
        product.reject('第一次理由')
        product.resubmit()
        product.refresh_from_db()
        self.assertEqual(product.status, 'pending')
        product.reject('第二次理由')
        product.refresh_from_db()
        self.assertEqual(product.status, 'rejected')
        reasons = list(
            RejectionNotice.objects.filter(product=product).values_list('reason', flat=True)
        )
        self.assertEqual(len(reasons), 2)
        self.assertEqual(set(reasons), {'第一次理由', '第二次理由'})

    # ---- 界面重提入口与 0 图守卫 ----
    def test_profile_resubmit_entry_shown_when_rejected(self):
        product = self._make_product()
        self._reject_with_reason(product)
        notice = RejectionNotice.objects.get(product=product)
        self.assertTrue(notice.can_resubmit)
        self._login()
        resp = self.client.get(reverse('profile'))
        self.assertContains(resp, '修改并重新提交')
        self.assertContains(resp, f'href="/listings/{product.pk}/resubmit/"')

    def test_profile_resubmit_entry_hidden_after_resubmit(self):
        product = self._make_product()
        self._attach_images(product, count=1, prefix='entry')
        self._reject_with_reason(product)
        self._login()
        self.client.post(reverse('resubmit', args=[product.pk]), self.valid_data)
        product.refresh_from_db()
        self.assertEqual(product.status, 'pending')
        notice = RejectionNotice.objects.get(product=product)
        self.assertFalse(notice.can_resubmit)
        resp = self.client.get(reverse('profile'))
        self.assertNotContains(resp, '修改并重新提交')
        self.assertNotContains(resp, f'/listings/{product.pk}/resubmit/')

    def test_zero_image_rejected_product_cannot_resubmit_without_images(self):
        product = self._make_product()
        self._reject_with_reason(product)
        notices_before = RejectionNotice.objects.count()
        self._login()
        resp = self.client.post(reverse('resubmit', args=[product.pk]), self.valid_data)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '该商品暂无图片，请至少上传 1 张商品图片')
        self.assertNotContains(resp, '已重新提交')
        product.refresh_from_db()
        self.assertEqual(product.status, 'rejected')
        self.assertEqual(product.title, '原商品标题')
        self.assertEqual(product.images.count(), 0)
        self.assertEqual(RejectionNotice.objects.count(), notices_before)


# ---------------------------------------------------------------------------
# Story 2.4：查看我的发布。本段自包含追加，不改动上方既有测试类。
# ---------------------------------------------------------------------------
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from listings.models import Product, ProductImage, RejectionNotice


class MyListingsViewTests(TestCase):
    """覆盖 spec-2-4 I/O 矩阵：两处空状态、四态中文展示、倒序、仅 rejected 重提入口、
    个人中心摘要与「查看全部」、他人数据隔离、登录门控、只读 405 / 无写入、未认证可读。"""

    def setUp(self):
        self.User = get_user_model()
        self.owner = self.User.objects.create_user(
            student_id='20242401', username='卖家甲', password='testpass12345'
        )
        self.other = self.User.objects.create_user(
            student_id='20242402', username='卖家乙', password='testpass12345'
        )
        self.url = reverse('my_listings')
        self.profile_url = reverse('profile')

    def _login(self, user=None):
        self.client.force_login(user or self.owner)

    def _make_product(self, owner, title, status='pending', price=Decimal('25.00'),
                      condition='良好', category='教材'):
        return Product.objects.create(
            owner=owner,
            title=title,
            description='描述文本',
            price=price,
            condition=condition,
            category=category,
            status=status,
        )

    def _four_status_products(self):
        specs = (
            ('本人待审核书', 'pending', Decimal('11.11'), '全新'),
            ('本人已上架书', 'approved', Decimal('22.22'), '良好'),
            ('本人已驳回书', 'rejected', Decimal('33.33'), '中等'),
            ('本人已下架书', 'offline', Decimal('44.44'), '全新'),
        )
        return [
            self._make_product(self.owner, title, status, price, condition)
            for title, status, price, condition in specs
        ]

    def _set_created_at(self, product, when):
        Product.objects.filter(pk=product.pk).update(created_at=when)
        product.refresh_from_db()
        return product

    def _snapshot(self):
        return list(
            Product.objects.values(
                'pk', 'owner_id', 'title', 'description', 'price', 'condition',
                'category', 'status', 'created_at', 'updated_at',
            ).order_by('pk')
        )

    # ---- 两处中文空状态 ----
    def test_standalone_page_empty_state(self):
        self._login()
        self.assertEqual(self.url, '/listings/mine/')
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'listings/my_listings.html')
        self.assertContains(resp, '我的发布')
        self.assertContains(resp, '暂无发布记录，你还没有发布任何商品')
        self.assertTrue(resp.context['my_listings_empty'])
        self.assertEqual(list(resp.context['my_listings']), [])
        self.assertNotContains(resp, '<img')
        self.assertNotContains(resp, '修改并重新提交')

    def test_profile_card_empty_state_and_four_sections_regression(self):
        self._login()
        resp = self.client.get(self.profile_url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['my_listings_empty'])
        self.assertEqual(list(resp.context['my_listings']), [])
        self.assertContains(resp, '暂无发布记录，你还没有发布任何商品')
        # accounts/tests.py:643-654 的四板块空状态断言不破
        self.assertContains(resp, '我的发布')
        self.assertContains(resp, '我的订单')
        self.assertContains(resp, '我的消息')
        self.assertContains(resp, '我的评价')
        self.assertContains(resp, '暂无订单记录')
        self.assertContains(resp, '暂无消息记录')
        self.assertContains(resp, '暂无评价记录')
        self.assertTrue(resp.context['my_orders_empty'])
        self.assertTrue(resp.context['my_messages_empty'])
        self.assertTrue(resp.context['my_reviews_empty'])
        # 「查看全部」入口始终指向独立页
        self.assertContains(resp, '查看全部')
        self.assertContains(resp, f'href="{self.url}"')

    # ---- 四态全展示、状态唯一来源、倒序 ----
    def test_four_statuses_show_chinese_display_and_fields(self):
        products = self._four_status_products()
        self._login()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['my_listings_empty'])
        for product in products:
            self.assertContains(resp, product.title)
            self.assertContains(resp, product.get_status_display())
            self.assertContains(resp, str(product.price))
            self.assertContains(resp, product.get_condition_display())
            self.assertContains(resp, product.created_at.strftime('%Y-%m-%d %H:%M'))
        for label in ('待审核', '已上架', '已驳回', '已下架'):
            self.assertContains(resp, label)
        self.assertNotContains(resp, '<img')

    def test_status_values_are_legal_and_display_from_choices(self):
        self._four_status_products()
        self._login()
        resp = self.client.get(self.url)
        statuses = {p.status for p in resp.context['my_listings']}
        self.assertEqual(statuses, {'pending', 'approved', 'offline', 'rejected'})
        choices = dict(Product.STATUS_CHOICES)
        for product in resp.context['my_listings']:
            self.assertEqual(product.get_status_display(), choices[product.status])

    def test_list_ordered_by_created_at_desc(self):
        products = self._four_status_products()
        now = timezone.now()
        for i, product in enumerate(products):
            self._set_created_at(product, now - timedelta(days=4 - i))
        self._login()
        resp = self.client.get(self.url)
        newest_first = list(reversed(products))
        self.assertEqual(
            [p.pk for p in resp.context['my_listings']],
            [p.pk for p in newest_first],
        )
        html = resp.content.decode()
        positions = [html.index(p.title) for p in newest_first]
        self.assertEqual(positions, sorted(positions))

    # ---- 仅 rejected 商品复用既有 resubmit 路由 ----
    def test_resubmit_link_only_on_rejected(self):
        products = self._four_status_products()
        by_status = {p.status: p for p in products}
        self._login()
        resp = self.client.get(self.url)
        self.assertContains(resp, '修改并重新提交', count=1)
        rejected_url = reverse('resubmit', args=[by_status['rejected'].pk])
        self.assertContains(resp, f'href="{rejected_url}"')
        for status in ('pending', 'approved', 'offline'):
            url = reverse('resubmit', args=[by_status[status].pk])
            self.assertNotContains(resp, f'href="{url}"')

    # ---- 个人中心摘要与入口 ----
    def test_profile_card_shows_summary_and_view_all_link(self):
        p1 = self._make_product(self.owner, '本人甲商品', 'approved')
        p2 = self._make_product(self.owner, '本人乙商品', 'offline')
        self._login()
        resp = self.client.get(self.profile_url)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['my_listings_empty'])
        self.assertContains(resp, '本人甲商品')
        self.assertContains(resp, '本人乙商品')
        self.assertContains(resp, '已上架')
        self.assertContains(resp, '已下架')
        self.assertContains(resp, '查看全部')
        self.assertContains(resp, f'href="{self.url}"')
        self.assertEqual(
            {p.pk for p in resp.context['my_listings']}, {p1.pk, p2.pk}
        )
        self.assertTrue(
            all(p.owner_id == self.owner.pk for p in resp.context['my_listings'])
        )

    # ---- 他人数据服务端隔离（含 response.context owner 断言）----
    def test_other_user_data_isolation(self):
        own = self._make_product(self.owner, '本人专属标题ABC', 'pending', Decimal('12.34'))
        others = [
            self._make_product(self.other, title, status, price, '中等')
            for status, title, price in (
                ('pending', '他人专属标题P', Decimal('9001.01')),
                ('approved', '他人专属标题A', Decimal('9002.02')),
                ('rejected', '他人专属标题R', Decimal('9003.03')),
                ('offline', '他人专属标题O', Decimal('9004.04')),
            )
        ]
        self._login()
        page = self.client.get(self.url)
        profile = self.client.get(self.profile_url)
        for resp in (page, profile):
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, '本人专属标题ABC')
            for other in others:
                self.assertNotContains(resp, other.title)
                self.assertNotContains(resp, str(other.price))
            self.assertTrue(
                all(p.owner_id == self.owner.pk for p in resp.context['my_listings'])
            )
        self.assertEqual([p.pk for p in page.context['my_listings']], [own.pk])

    # ---- 登录门控 ----
    def test_unauthenticated_redirects_to_login_with_next(self):
        product = self._make_product(self.owner, '匿名不可见标题', 'approved')
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, f'/login/?next={self.url}')
        followed = self.client.get(self.url, follow=True)
        self.assertNotContains(followed, product.title)

    def test_unauthenticated_post_also_redirects(self):
        resp = self.client.post(self.url, {'foo': 'bar'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, f'/login/?next={self.url}')

    # ---- 只读：405 / 无写入 ----
    def test_read_only_methods_return_405_without_writes(self):
        self._four_status_products()
        self._login()
        before = self._snapshot()
        for method in (self.client.post, self.client.put, self.client.patch, self.client.delete):
            resp = method(self.url, {'title': 'hacked'})
            self.assertEqual(resp.status_code, 405, msg=method)
            self.assertEqual(resp['Allow'], 'GET, HEAD')
        self.assertEqual(self.client.head(self.url).status_code, 200)
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(ProductImage.objects.count(), 0)
        self.assertEqual(RejectionNotice.objects.count(), 0)

    def test_get_is_read_only_on_both_pages(self):
        self._four_status_products()
        self._login()
        before = self._snapshot()
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.get(self.profile_url).status_code, 200)
        self.assertEqual(self._snapshot(), before)

    # ---- 未认证用户可读 ----
    def test_unverified_user_can_read_own_data(self):
        product = self._make_product(self.owner, '未认证卖家本人商品', 'pending')
        self.assertFalse(self.owner.is_verified)
        self._login()
        page = self.client.get(self.url)
        profile = self.client.get(self.profile_url)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(profile.status_code, 200)
        self.assertContains(page, '未认证卖家本人商品')
        self.assertContains(page, product.get_status_display())
        self.assertContains(profile, '未认证卖家本人商品')
        self.assertFalse(page.context['my_listings_empty'])
