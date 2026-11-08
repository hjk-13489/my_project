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
