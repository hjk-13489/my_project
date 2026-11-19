from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from accounts.views import PROFILE_ORDERS_SUMMARY_LIMIT
from listings.models import Product
from orders.forms import OrderCreateForm, RefundRequestForm, ReviewForm
from orders.models import InvalidTransition, Order, RefundRequest, Review
from orders.views import (
    REFUND_STATUS_ERROR, REVIEW_DUPLICATE_ERROR, REVIEW_STATUS_ERROR,
)


class OrderStateMachineTests(TestCase):
    """订单状态机：覆盖 I/O 矩阵全部场景，非法转移必须显式拒绝且不落库。"""

    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            student_id='2023001', username='卖家', password='test123456'
        )
        cls.buyer = User.objects.create_user(
            student_id='2023002', username='买家', password='test123456'
        )
        cls.product = Product.objects.create(
            owner=cls.seller,
            title='线性代数教材',
            description='九成新',
            price=Decimal('30.00'),
            condition='良好',
            category='教材',
            status='approved',
        )

    # ---------- helpers ----------
    def _make_order(self, status='pending_payment'):
        """构造指定状态的订单夹具（直接赋值 status 属测试夹具，非业务写入路径）。"""
        return Order.objects.create(
            buyer=self.buyer,
            product=self.product,
            price=self.product.price,
            status=status,
        )

    def _assert_rejected(self, order, method_name, *args):
        """断言指定转移抛 InvalidTransition，且数据库中的状态保持原样。"""
        original = order.status
        with self.assertRaises(InvalidTransition):
            getattr(order, method_name)(*args)
        order.refresh_from_db()
        self.assertEqual(order.status, original)

    # ---------- 正常路径 ----------
    def test_normal_path_pay_then_confirm_receipt(self):
        order = self._make_order()

        order.pay()
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')

        order.confirm_receipt()
        order.refresh_from_db()
        self.assertEqual(order.status, 'completed')

    def test_mark_reviewed_after_completed(self):
        order = self._make_order(status='completed')

        order.mark_reviewed()
        order.refresh_from_db()
        self.assertEqual(order.status, 'reviewed')

    # ---------- 退款分支 ----------
    def test_refund_approved(self):
        order = self._make_order(status='paid')

        order.request_refund()
        order.refresh_from_db()
        self.assertEqual(order.status, 'dispute')

        order.resolve_refund(True)
        order.refresh_from_db()
        self.assertEqual(order.status, 'refunded')

    def test_refund_rejected(self):
        order = self._make_order(status='dispute')

        order.resolve_refund(False)
        order.refresh_from_db()
        self.assertEqual(order.status, 'refund_failed')

    def test_resolve_refund_requires_dispute(self):
        for status in ('pending_payment', 'paid', 'received', 'completed', 'reviewed'):
            order = self._make_order(status=status)
            self._assert_rejected(order, 'resolve_refund', True)
            self._assert_rejected(order, 'resolve_refund', False)

    def test_resolve_refund_rejects_non_bool(self):
        """'false' / '0' 等字符串不得按真值被记成「退款成功」。"""
        for value in ('false', '0', '', 0, 1, None):
            order = self._make_order(status='dispute')
            with self.assertRaises(ValueError):
                order.resolve_refund(value)
            order.refresh_from_db()
            self.assertEqual(order.status, 'dispute')

    # ---------- 非法转移 ----------
    def test_confirm_receipt_without_payment_rejected(self):
        order = self._make_order()
        self._assert_rejected(order, 'confirm_receipt')

    def test_request_refund_after_receipt_rejected(self):
        """收货后（已确认收货 / 已完成）不可再发起退款。"""
        for status in ('received', 'completed'):
            order = self._make_order(status=status)
            self._assert_rejected(order, 'request_refund')

    def test_request_refund_when_pending_payment_rejected(self):
        order = self._make_order()
        self._assert_rejected(order, 'request_refund')

    def test_pay_twice_rejected(self):
        order = self._make_order(status='paid')
        self._assert_rejected(order, 'pay')

    def test_confirm_receipt_twice_rejected(self):
        order = self._make_order(status='completed')
        self._assert_rejected(order, 'confirm_receipt')

    def test_mark_reviewed_requires_completed(self):
        """互评仅限已完成：未收货/未交付的订单不得直接进入「已互评」。"""
        for status in ('pending_payment', 'paid', 'received'):
            order = self._make_order(status=status)
            self._assert_rejected(order, 'mark_reviewed')

    def test_dispute_rejects_ordinary_transitions(self):
        """纠纷单只能由管理员裁决，不能支付、收货、互评或重复发起退款。"""
        for method_name in ('pay', 'confirm_receipt', 'mark_reviewed', 'request_refund'):
            order = self._make_order(status='dispute')
            self._assert_rejected(order, method_name)

    def test_stale_instance_cannot_overwrite_concurrent_state(self):
        """A 已退款进入纠纷后，仍持「待交付」的陈旧 B 不得把订单改成已完成。"""
        order = self._make_order(status='paid')
        stale = Order.objects.get(pk=order.pk)

        order.request_refund()
        self.assertEqual(Order.objects.get(pk=order.pk).status, 'dispute')

        with self.assertRaises(InvalidTransition):
            stale.confirm_receipt()
        stale.refresh_from_db()
        self.assertEqual(stale.status, 'dispute')
        self.assertEqual(Order.objects.get(pk=order.pk).status, 'dispute')

    def test_confirm_receipt_rolls_back_first_hop_when_second_fails(self):
        """两跳同事务：第二跳失败时首跳的 received 必须回滚。"""
        order = self._make_order(status='paid')
        real_transition = Order._transition

        def flaky(instance, target):
            if target == 'completed':
                raise InvalidTransition('模拟第二跳失败')
            return real_transition(instance, target)

        with mock.patch.object(Order, '_transition', new=flaky):
            with self.assertRaises(InvalidTransition):
                order.confirm_receipt()

        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')

    def test_terminal_states_reject_every_transition(self):
        movements = [
            ('pay', ()),
            ('confirm_receipt', ()),
            ('request_refund', ()),
            ('mark_reviewed', ()),
            ('resolve_refund', (True,)),
            ('resolve_refund', (False,)),
        ]
        for status in ('reviewed', 'refunded', 'refund_failed'):
            order = self._make_order(status=status)
            for method_name, args in movements:
                self._assert_rejected(order, method_name, *args)

    # ---------- 字段约定 ----------
    def test_new_order_defaults_to_pending_payment(self):
        """不传 status 建单必须落在「待支付」：4.1 的下单视图依赖该默认值。"""
        order = Order.objects.create(
            buyer=self.buyer,
            product=self.product,
            price=self.product.price,
        )
        self.assertEqual(order.status, 'pending_payment')
        order.refresh_from_db()
        self.assertEqual(order.status, 'pending_payment')

    def test_price_is_snapshot(self):
        """价格是下单时快照：商品改价不影响已有订单。"""
        product = Product.objects.create(
            owner=self.seller,
            title='快照专用教材',
            description='仅供价格快照断言，避免改动共享商品',
            price=Decimal('30.00'),
            condition='良好',
            category='教材',
            status='approved',
        )
        order = Order.objects.create(
            buyer=self.buyer,
            product=product,
            price=product.price,
        )
        self.assertEqual(order.price, Decimal('30.00'))

        product.price = Decimal('99.00')
        product.save(update_fields=['price'])

        order.refresh_from_db()
        self.assertEqual(order.price, Decimal('30.00'))


class OrderCreateViewTests(TestCase):
    """4.1 下单创建订单：视图层覆盖 I/O 矩阵 13 行，不改动状态机既有 18 例。"""

    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            student_id='2023101', username='卖家', password='test123456'
        )
        cls.buyer = User.objects.create_user(
            student_id='2023102', username='买家', password='test123456'
        )
        cls.other = User.objects.create_user(
            student_id='2023103', username='路人', password='test123456'
        )
        cls.product = Product.objects.create(
            owner=cls.seller, title='线性代数教材', description='九成新',
            price=Decimal('30.00'), condition='良好', category='教材',
            status='approved',
        )
        cls.pending_product = Product.objects.create(
            owner=cls.seller, title='待审核商品', description='x',
            price=Decimal('10.00'), condition='良好', category='教材', status='pending',
        )
        cls.rejected_product = Product.objects.create(
            owner=cls.seller, title='已驳回商品', description='x',
            price=Decimal('10.00'), condition='良好', category='教材', status='rejected',
        )
        cls.offline_product = Product.objects.create(
            owner=cls.seller, title='已下架商品', description='x',
            price=Decimal('10.00'), condition='良好', category='教材', status='offline',
        )

    def _create_url(self, product=None):
        return reverse('order_create', kwargs={'product_pk': (product or self.product).pk})

    def _detail_url(self, order):
        return reverse('order_detail', kwargs={'pk': order.pk})

    def _login(self, user):
        self.client.login(username=user.student_id, password='test123456')

    # 1 确认页
    def test_confirm_page_get(self):
        self._login(self.buyer)
        response = self.client.get(self._create_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.title)
        self.assertContains(response, str(self.product.price))
        self.assertContains(response, self.seller.username)
        self.assertContains(response, '确认下单')
        self.assertContains(response, 'name="message"')
        self.assertEqual(Order.objects.count(), 0)

    # 2 成功建单 + 302 落点 + 字段归属
    def test_create_order_success_and_redirect(self):
        self._login(self.buyer)
        response = self.client.post(self._create_url(), {'message': '当面交易'})
        order = Order.objects.get(product=self.product)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self._detail_url(order))
        self.assertEqual(order.buyer, self.buyer)
        self.assertEqual(order.product, self.product)
        self.assertEqual(order.status, 'pending_payment')
        self.assertEqual(order.price, self.product.price)
        self.assertEqual(order.message, '当面交易')

    # 3 留言为空
    def test_empty_message_allowed(self):
        self._login(self.buyer)
        response = self.client.post(self._create_url(), {'message': ''})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.get(product=self.product).message, '')

    # 4 价格快照（视图级）
    def test_price_snapshot_after_product_price_change(self):
        self._login(self.buyer)
        self.client.post(self._create_url(), {'message': ''})
        order = Order.objects.get(product=self.product)
        self.product.price = Decimal('99.00')
        self.product.save(update_fields=['price'])
        order.refresh_from_db()
        self.assertEqual(order.price, Decimal('30.00'))

    # 5 留言超长
    def test_message_too_long_rejected(self):
        self._login(self.buyer)
        response = self.client.post(self._create_url(), {'message': '字' * 501})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)
        self.assertContains(response, '留言不能超过 500 个字符')
        self.assertIn('message', response.context['form'].errors)

    # 6 不可见商品 GET/POST → 404，无订单
    def test_invisible_products_404(self):
        self._login(self.buyer)
        for product in (self.pending_product, self.rejected_product, self.offline_product):
            for method in ('get', 'post'):
                with self.subTest(product=product.title, method=method):
                    response = getattr(self.client, method)(
                        self._create_url(product), {'message': ''}
                    )
                    self.assertEqual(response.status_code, 404)
        missing = reverse('order_create', kwargs={'product_pk': 999999})
        self.assertEqual(self.client.get(missing).status_code, 404)
        self.assertEqual(self.client.post(missing, {'message': ''}).status_code, 404)
        self.assertEqual(Order.objects.count(), 0)

    # 7 未登录 GET/POST → 302 到登录页
    def test_anonymous_redirected_to_login(self):
        for method in ('get', 'post'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    self._create_url(), {'message': ''}
                )
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith('/login/'))
                self.assertIn('next=', response.url)
        self.assertEqual(Order.objects.count(), 0)

    # 8 非法方法 PUT/DELETE → 405
    def test_unsafe_methods_405(self):
        self._login(self.buyer)
        for method in ('put', 'delete'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self._create_url())
                self.assertEqual(response.status_code, 405)
        self.assertEqual(Order.objects.count(), 0)

    # 9 卖家自买
    def test_seller_cannot_buy_own_product(self):
        self._login(self.seller)
        response = self.client.post(self._create_url(), {'message': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)
        self.assertContains(response, '不能购买自己发布的商品')
        self.assertIn(
            '不能购买自己发布的商品',
            response.context['form'].non_field_errors(),
        )

    # 10 重复下单（进行中）
    def test_duplicate_in_progress_order_rejected(self):
        self._login(self.buyer)
        for status in ('pending_payment', 'paid', 'received', 'dispute'):
            with self.subTest(status=status):
                Order.objects.all().delete()
                Order.objects.create(
                    buyer=self.buyer, product=self.product,
                    price=self.product.price, status=status,
                )
                response = self.client.post(self._create_url(), {'message': ''})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(Order.objects.count(), 1)
                self.assertContains(response, '该商品已有进行中的订单')

    # 11 已收尾可再下单
    def test_reorder_allowed_when_only_closed_orders(self):
        self._login(self.buyer)
        for status in ('completed', 'reviewed', 'refunded', 'refund_failed'):
            with self.subTest(status=status):
                Order.objects.all().delete()
                Order.objects.create(
                    buyer=self.buyer, product=self.product,
                    price=self.product.price, status=status,
                )
                response = self.client.post(self._create_url(), {'message': '再下一单'})
                self.assertEqual(response.status_code, 302)
                fresh = Order.objects.filter(status='pending_payment')
                self.assertEqual(fresh.count(), 1)
                self.assertEqual(fresh.first().buyer, self.buyer)

    # 12 本人订单详情
    def test_owner_can_view_order_detail(self):
        self._login(self.buyer)
        self.client.post(self._create_url(), {'message': '留个言'})
        order = Order.objects.get(product=self.product)
        detail = self.client.get(self._detail_url(order))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, self.product.title)
        self.assertContains(detail, str(order.price))
        self.assertContains(detail, '留个言')
        self.assertContains(detail, '待支付')

    # 13 他人订单详情 → 404
    def test_other_user_order_detail_404(self):
        self._login(self.buyer)
        self.client.post(self._create_url(), {'message': ''})
        order = Order.objects.get(product=self.product)
        self.client.logout()
        self._login(self.other)
        self.assertEqual(self.client.get(self._detail_url(order)).status_code, 404)

    # 服务端推导：price/buyer/product 不得被请求参数篡改
    def test_server_derived_fields_ignore_forged_post_data(self):
        self._login(self.buyer)
        response = self.client.post(self._create_url(), {
            'message': '照常下单',
            'price': '0.01',
            'buyer': self.other.pk,
            'product': self.pending_product.pk,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.get()
        self.assertEqual(order.price, self.product.price)
        self.assertEqual(order.buyer, self.buyer)
        self.assertEqual(order.product, self.product)
        self.assertEqual(order.product.status, 'approved')
        self.assertEqual(list(OrderCreateForm().fields), ['message'])

    # 订单详情 @login_required 回归保护
    def test_order_detail_anonymous_redirected_to_login(self):
        order = Order.objects.create(
            buyer=self.buyer, product=self.product, price=self.product.price,
        )
        response = self.client.get(self._detail_url(order))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/login/'))
        self.assertIn('next=', response.url)

    # 订单详情 @require_safe 回归保护
    def test_order_detail_rejects_unsafe_methods(self):
        self._login(self.buyer)
        order = Order.objects.create(
            buyer=self.buyer, product=self.product, price=self.product.price,
        )
        url = self._detail_url(order)
        for method in ('post', 'put', 'delete'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 405)


class OrderPayViewTests(TestCase):
    """4.2 模拟支付：视图层覆盖 I/O 矩阵全部 10 行，不改动既有 34 例。"""

    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            student_id='2023201', username='卖家', password='test123456'
        )
        cls.buyer = User.objects.create_user(
            student_id='2023202', username='买家', password='test123456'
        )
        cls.other = User.objects.create_user(
            student_id='2023203', username='路人', password='test123456'
        )
        cls.product = Product.objects.create(
            owner=cls.seller, title='线性代数教材', description='x',
            price=Decimal('30.00'), condition='良好', category='教材',
            status='approved',
        )

    # ---------- helpers ----------
    def _make_order(self, status='pending_payment'):
        return Order.objects.create(
            buyer=self.buyer,
            product=self.product,
            price=self.product.price,
            status=status,
        )

    def _pay_url(self, order):
        return reverse('order_pay', kwargs={'pk': order.pk})

    def _detail_url(self, order):
        return reverse('order_detail', kwargs={'pk': order.pk})

    def _login(self, user):
        self.client.login(username=user.student_id, password='test123456')

    # 1 正常支付：成功流转且 DB 重读、302 落点、徽章与按钮
    def test_pay_success_transitions_and_redirects(self):
        order = self._make_order()
        self._login(self.buyer)
        order.refresh_from_db()
        before = order.updated_at

        response = self.client.post(self._pay_url(order))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self._detail_url(order))
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')
        self.assertGreater(order.updated_at, before)
        self.assertEqual(Order.objects.count(), 1)  # 不新增订单/支付流水

        detail = self.client.get(self._detail_url(order))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, '已支付/待交付')
        self.assertNotContains(detail, '模拟支付')
        self.assertNotContains(detail, self._pay_url(order))

    # 2 按钮门控：仅 pending_payment 渲染支付表单，其余状态只显示徽章
    def test_pay_button_only_shown_when_pending_payment(self):
        self._login(self.buyer)
        pending = self._make_order(status='pending_payment')
        detail = self.client.get(self._detail_url(pending))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, self._pay_url(pending))
        self.assertContains(detail, '模拟支付')
        self.assertContains(detail, 'csrfmiddlewaretoken')

        for status in ('paid', 'received', 'completed', 'reviewed',
                       'dispute', 'refunded', 'refund_failed'):
            order = self._make_order(status=status)
            with self.subTest(status=status):
                detail = self.client.get(self._detail_url(order))
                self.assertEqual(detail.status_code, 200)
                self.assertNotContains(detail, self._pay_url(order))
                self.assertNotContains(detail, '模拟支付')
                self.assertContains(detail, order.get_status_display())

    # 2b 表单以 POST 提交并走通支付：method/action 正确，提交后 302 且状态流转
    def test_pay_form_is_post_and_completes_payment(self):
        order = self._make_order(status='pending_payment')
        self._login(self.buyer)

        detail = self.client.get(self._detail_url(order))
        self.assertEqual(detail.status_code, 200)
        # 合并断言：支付表单确为 POST 且 action 指向 order_pay
        # （合并可避免被导航栏登出表单的 method="post" 误命中）
        self.assertContains(
            detail,
            '<form method="post" action="%s"' % self._pay_url(order),
        )

        # 按该 action 提交，走通支付
        response = self.client.post(self._pay_url(order))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self._detail_url(order))
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')

    # 3 非法方法：已登录 GET/PUT/DELETE → 405，状态不变
    def test_non_post_methods_405(self):
        order = self._make_order()
        self._login(self.buyer)
        for method in ('get', 'put', 'delete'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self._pay_url(order))
                self.assertEqual(response.status_code, 405)
        order.refresh_from_db()
        self.assertEqual(order.status, 'pending_payment')

    # 4 未登录：匿名 GET/POST 一律 302 到登录页（带 next），状态不变
    def test_anonymous_redirected_to_login(self):
        order = self._make_order()
        for method in ('get', 'post'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self._pay_url(order))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith('/login/'))
                self.assertIn('next=', response.url)
        order.refresh_from_db()
        self.assertEqual(order.status, 'pending_payment')

    # 5 他人订单：非 buyer POST → 404，状态不变
    def test_other_user_order_404(self):
        order = self._make_order()
        self._login(self.other)
        response = self.client.post(self._pay_url(order))
        self.assertEqual(response.status_code, 404)
        order.refresh_from_db()
        self.assertEqual(order.status, 'pending_payment')

    # 6 不存在订单：不存在的 pk → 404
    def test_nonexistent_order_404(self):
        self._login(self.buyer)
        url = reverse('order_pay', kwargs={'pk': 999999})
        self.assertEqual(self.client.post(url).status_code, 404)

    # 7 重复支付：非待支付/终态 POST → 200 重渲染 + 可见错误条，
    #    状态与 updated_at 均不变，且不渲染支付表单
    def test_duplicate_pay_rejected_with_error_bar(self):
        self._login(self.buyer)
        for status in ('paid', 'received', 'completed', 'reviewed',
                       'dispute', 'refunded', 'refund_failed'):
            order = self._make_order(status=status)
            order.refresh_from_db()
            before = order.updated_at
            with self.subTest(status=status):
                response = self.client.post(self._pay_url(order))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'alert-danger')
                self.assertContains(response, '支付被拒绝：订单当前状态不允许支付，请勿重复提交；当前状态以上方状态徽章为准')
                self.assertIn('pay_error', response.context)
                self.assertContains(response, order.get_status_display())
                self.assertNotContains(response, self._pay_url(order))
                order.refresh_from_db()
                self.assertEqual(order.status, status)
                self.assertEqual(order.updated_at, before)

    # 8a 连续两次提交：恰好一次流转到 paid，第二次被状态机拒绝且可见
    def test_double_submit_transitions_only_once(self):
        order = self._make_order(status='pending_payment')
        self._login(self.buyer)
        first = self.client.post(self._pay_url(order))
        self.assertEqual(first.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')
        before = order.updated_at

        second = self.client.post(self._pay_url(order))

        self.assertEqual(second.status_code, 200)
        self.assertContains(second, 'alert-danger')
        self.assertContains(second, '支付被拒绝：订单当前状态不允许支付，请勿重复提交；当前状态以上方状态徽章为准')
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')
        self.assertEqual(order.updated_at, before)

    # 8b 并发/陈旧实例：取到「待支付」实例后库内已被并发推进，
    #     条件更新挡住二次流转，给可见拒绝提示
    def test_concurrent_stale_instance_rejected_visibly(self):
        order = self._make_order(status='pending_payment')
        self._login(self.buyer)
        # 模拟并发请求先把库内状态推进到 paid（不影响内存中 order 的 status）
        Order.objects.filter(pk=order.pk).update(status='paid')

        def stale_lookup(model, *args, **kwargs):
            return order  # 陈旧实例：status 仍为 pending_payment

        with mock.patch('orders.views.get_object_or_404', side_effect=stale_lookup):
            response = self.client.post(self._pay_url(order))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'alert-danger')
        self.assertContains(response, '支付被拒绝：订单当前状态不允许支付，请勿重复提交；当前状态以上方状态徽章为准')
        self.assertNotContains(response, self._pay_url(order))
        self.assertIn('pay_error', response.context)
        # 恰好一次流转：库内保持 paid，陈旧实例未能二次改写
        self.assertEqual(Order.objects.get(pk=order.pk).status, 'paid')

    # 9 伪造字段：POST 携带 status/price/buyer/product 全部被忽略，仅 pay() 流转
    def test_forged_post_fields_ignored(self):
        order = self._make_order(status='pending_payment')
        self._login(self.buyer)
        response = self.client.post(self._pay_url(order), {
            'status': 'paid',
            'price': '0.01',
            'buyer': self.other.pk,
            'product': 999999,
        })
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')
        self.assertEqual(order.price, self.product.price)
        self.assertEqual(order.buyer, self.buyer)
        self.assertEqual(order.product, self.product)

    # 10 支付后商品改价/下架：订单 price 与 status 均不变
    def test_product_price_change_after_pay_does_not_affect_order(self):
        order = self._make_order(status='pending_payment')
        self._login(self.buyer)
        self.client.post(self._pay_url(order))
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')
        before_price = order.price
        before_status = order.status

        self.product.price = Decimal('999.00')
        self.product.status = 'offline'
        self.product.save(update_fields=['price', 'status'])

        order.refresh_from_db()
        self.assertEqual(order.price, before_price)
        self.assertEqual(order.status, before_status)


class OrderConfirmReceiptViewTests(TestCase):
    """4.6 确认收货：视图层覆盖 I/O 矩阵，照搬 4.2 order_pay 的 HTTP 层范式。"""

    RECEIPT_ERROR = (
        '收货被拒绝：订单当前状态不允许确认收货，请勿重复提交；'
        '当前状态以上方状态徽章为准'
    )

    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            student_id='2024201', username='卖家', password='test123456'
        )
        cls.buyer = User.objects.create_user(
            student_id='2024202', username='买家', password='test123456'
        )
        cls.other = User.objects.create_user(
            student_id='2024203', username='路人', password='test123456'
        )
        cls.product = Product.objects.create(
            owner=cls.seller, title='线性代数教材', description='x',
            price=Decimal('30.00'), condition='良好', category='教材',
            status='approved',
        )

    # ---------- helpers ----------
    def _make_order(self, status='paid'):
        return Order.objects.create(
            buyer=self.buyer, product=self.product,
            price=self.product.price, status=status,
        )

    def _receipt_url(self, order):
        return reverse('order_confirm_receipt', kwargs={'pk': order.pk})

    def _detail_url(self, order):
        return reverse('order_detail', kwargs={'pk': order.pk})

    def _login(self, user):
        self.client.login(username=user.student_id, password='test123456')

    # 1 正常收货：两跳落 completed（received 为事务中间态不对外可见），
    #    302 落点、updated_at 更新、成功后不再渲染收货按钮
    def test_confirm_receipt_success_transitions_and_redirects(self):
        order = self._make_order()
        self._login(self.buyer)
        order.refresh_from_db()
        before = order.updated_at

        response = self.client.post(self._receipt_url(order))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self._detail_url(order))
        order.refresh_from_db()
        self.assertEqual(order.status, 'completed')
        self.assertGreater(order.updated_at, before)
        self.assertEqual(Order.objects.count(), 1)  # 不新增订单

        detail = self.client.get(self._detail_url(order))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, '已完成')
        self.assertNotContains(detail, '确认收货')
        self.assertNotContains(detail, self._receipt_url(order))

    # 2 按钮门控：仅 paid 渲染收货表单；其余状态只显示徽章与链接
    #    （received 的徽章文案本身含「确认收货」，故以表单 URL 判定按钮有无）
    def test_receipt_button_only_shown_when_paid(self):
        self._login(self.buyer)
        paid = self._make_order(status='paid')
        detail = self.client.get(self._detail_url(paid))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, self._receipt_url(paid))
        self.assertContains(detail, '确认收货')
        self.assertContains(detail, 'csrfmiddlewaretoken')

        for status in ('pending_payment', 'received', 'completed', 'reviewed',
                       'dispute', 'refunded', 'refund_failed'):
            order = self._make_order(status=status)
            with self.subTest(status=status):
                detail = self.client.get(self._detail_url(order))
                self.assertEqual(detail.status_code, 200)
                self.assertNotContains(detail, self._receipt_url(order))
                self.assertContains(detail, order.get_status_display())

    # 2b 表单以 POST 提交并走通收货：method/action 正确，提交后 302 且状态流转
    def test_receipt_form_is_post_and_completes_receipt(self):
        order = self._make_order(status='paid')
        self._login(self.buyer)

        detail = self.client.get(self._detail_url(order))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(
            detail,
            '<form method="post" action="%s"' % self._receipt_url(order),
        )

        response = self.client.post(self._receipt_url(order))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self._detail_url(order))
        order.refresh_from_db()
        self.assertEqual(order.status, 'completed')

    # 3 非法方法：已登录 GET/PUT/DELETE → 405（Allow: POST），状态不变
    def test_non_post_methods_405(self):
        order = self._make_order()
        self._login(self.buyer)
        for method in ('get', 'put', 'delete'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self._receipt_url(order))
                self.assertEqual(response.status_code, 405)
                self.assertEqual(response['Allow'], 'POST')
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')

    # 4 未登录：匿名 GET/POST 一律 302 到登录页（带 next），状态不变
    def test_anonymous_redirected_to_login(self):
        order = self._make_order()
        for method in ('get', 'post'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self._receipt_url(order))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith('/login/'))
                self.assertIn('next=', response.url)
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')

    # 5 他人订单：非 buyer POST → 404，状态不变
    def test_other_user_order_404(self):
        order = self._make_order()
        self._login(self.other)
        response = self.client.post(self._receipt_url(order))
        self.assertEqual(response.status_code, 404)
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')

    # 6 不存在订单：不存在的 pk → 404
    def test_nonexistent_order_404(self):
        self._login(self.buyer)
        url = reverse('order_confirm_receipt', kwargs={'pk': 999999})
        self.assertEqual(self.client.post(url).status_code, 404)

    # 7 非法/重复状态：POST → 200 重渲染 + 可见错误条，状态与 updated_at
    #    均不变，且不再渲染收货表单（以表单 URL 判定）
    def test_invalid_transitions_rejected_with_error_bar(self):
        self._login(self.buyer)
        for status in ('pending_payment', 'received', 'completed', 'reviewed',
                       'dispute', 'refunded', 'refund_failed'):
            order = self._make_order(status=status)
            order.refresh_from_db()
            before = order.updated_at
            with self.subTest(status=status):
                response = self.client.post(self._receipt_url(order))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'alert-danger')
                self.assertContains(response, self.RECEIPT_ERROR)
                self.assertIn('receipt_error', response.context)
                self.assertContains(response, order.get_status_display())
                self.assertNotContains(response, self._receipt_url(order))
                order.refresh_from_db()
                self.assertEqual(order.status, status)
                self.assertEqual(order.updated_at, before)

    # 8a 连续两次提交：恰好一次流转到 completed，第二次被状态机拒绝且可见
    def test_double_submit_transitions_only_once(self):
        order = self._make_order(status='paid')
        self._login(self.buyer)
        first = self.client.post(self._receipt_url(order))
        self.assertEqual(first.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, 'completed')
        before = order.updated_at

        second = self.client.post(self._receipt_url(order))

        self.assertEqual(second.status_code, 200)
        self.assertContains(second, 'alert-danger')
        self.assertContains(second, self.RECEIPT_ERROR)
        order.refresh_from_db()
        self.assertEqual(order.status, 'completed')
        self.assertEqual(order.updated_at, before)

    # 8b 并发/陈旧实例：取到「已支付」实例后库内已被并发推进到 dispute，
    #    条件更新挡住二次流转；refresh_from_db 后徽章显示库内真实状态
    def test_concurrent_stale_instance_rejected_visibly(self):
        order = self._make_order(status='paid')
        self._login(self.buyer)
        # 模拟并发请求先把库内状态推进到 dispute（不影响内存中 order 的 status）
        Order.objects.filter(pk=order.pk).update(status='dispute')

        def stale_lookup(model, *args, **kwargs):
            return order  # 陈旧实例：status 仍为 paid

        with mock.patch('orders.views.get_object_or_404', side_effect=stale_lookup):
            response = self.client.post(self._receipt_url(order))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'alert-danger')
        self.assertContains(response, self.RECEIPT_ERROR)
        self.assertNotContains(response, self._receipt_url(order))
        self.assertIn('receipt_error', response.context)
        self.assertContains(response, '纠纷')  # 徽章反映库内真实状态
        self.assertEqual(Order.objects.get(pk=order.pk).status, 'dispute')

    # 9 伪造字段：POST 携带 status 等字段全部被忽略，仅 confirm_receipt() 流转
    def test_forged_post_fields_ignored(self):
        order = self._make_order(status='paid')
        self._login(self.buyer)
        response = self.client.post(self._receipt_url(order), {
            'status': 'completed',
            'price': '0.01',
            'buyer': self.other.pk,
            'product': 999999,
        })
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, 'completed')
        self.assertEqual(order.price, self.product.price)
        self.assertEqual(order.buyer, self.buyer)
        self.assertEqual(order.product, self.product)

    # 注：I/O 矩阵「收货后退款不可达」由模型层既有测试
    #    OrderStateMachineTests.test_request_refund_after_receipt_rejected 覆盖，
    #    本故事不新增退款 UI 或模型层重复用例。


class OrderContactViewTests(TestCase):
    """4.3 下单后展示联系方式：按订单状态门控，覆盖 I/O 矩阵全部 9 行。"""

    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            student_id='2023301', username='卖家昵称', password='test123456',
            qq='88001234567', wechat='wx_seller_4_3',
        )
        cls.buyer = User.objects.create_user(
            student_id='2023302', username='买家', password='test123456'
        )
        cls.other = User.objects.create_user(
            student_id='2023303', username='路人', password='test123456'
        )
        cls.product = Product.objects.create(
            owner=cls.seller, title='线性代数教材', description='x',
            price=Decimal('30.00'), condition='良好', category='教材',
            status='approved',
        )

    # ---------- helpers ----------
    def _make_order(self, status='pending_payment'):
        return Order.objects.create(
            buyer=self.buyer, product=self.product,
            price=self.product.price, status=status,
        )

    def _detail_url(self, order):
        return reverse('order_detail', kwargs={'pk': order.pk})

    def _pay_url(self, order):
        return reverse('order_pay', kwargs={'pk': order.pk})

    def _login(self, user):
        self.client.login(username=user.student_id, password='test123456')

    # 1 待支付：整个联系方式区块、值与认证徽章均不输出，支付按钮仍在
    def test_pending_payment_hides_contact_block_and_badge(self):
        order = self._make_order()
        self._login(self.buyer)
        response = self.client.get(self._detail_url(order))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '卖家联系方式')
        self.assertNotContains(response, 'QQ')
        self.assertNotContains(response, '微信')
        self.assertNotContains(response, self.seller.qq)
        self.assertNotContains(response, self.seller.wechat)
        # base.html 导航栏会为当前登录用户渲染认证徽章，故用联系方式区块
        # 独有的锚点判定，避免把全局导航徽章误当作卖家认证徽章。
        self.assertNotContains(response, self.seller.username)
        self.assertNotContains(response, 'QQ：')
        self.assertNotContains(response, '微信：')
        self.assertContains(response, self._pay_url(order))
        self.assertContains(response, '模拟支付')

    # 2 已支付：展示 QQ/微信 + 认证状态，支付按钮消失
    def test_paid_order_shows_contact_and_verification_badge(self):
        order = self._make_order(status='paid')
        self._login(self.buyer)
        response = self.client.get(self._detail_url(order))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '卖家联系方式')
        self.assertContains(response, self.seller.username)
        self.assertContains(response, self.seller.qq)
        self.assertContains(response, self.seller.wechat)
        seller_line = response.content.decode().split('卖家：', 1)[1][:200]
        self.assertIn('待认证', seller_line)
        self.assertNotIn('✓ 已认证', seller_line)
        self.assertContains(response, order.get_status_display())
        self.assertNotContains(response, self._pay_url(order))
        self.assertNotContains(response, '模拟支付')

    # 2b 认证位为 True 时切换到「已认证」徽章
    def test_verified_seller_shows_verified_badge(self):
        self.seller.is_verified = True
        self.seller.save(update_fields=['is_verified'])
        order = self._make_order(status='paid')
        self._login(self.buyer)
        response = self.client.get(self._detail_url(order))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '✓ 已认证', count=1)
        seller_line = response.content.decode().split('卖家：', 1)[1][:200]
        self.assertIn('✓ 已认证', seller_line)
        self.assertNotIn('待认证', seller_line)
        self.assertContains(response, self.seller.qq)
        self.assertContains(response, self.seller.wechat)

    # 3 之后状态：7 个非待支付状态逐一展示，门控与状态徽章一致
    def test_later_states_all_show_contact(self):
        self._login(self.buyer)
        for status in ('received', 'completed', 'reviewed',
                       'dispute', 'refunded', 'refund_failed'):
            with self.subTest(status=status):
                order = self._make_order(status=status)
                response = self.client.get(self._detail_url(order))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, '卖家联系方式')
                self.assertContains(response, self.seller.qq)
                self.assertContains(response, self.seller.wechat)
                self.assertContains(response, order.get_status_display())
                self.assertNotContains(response, self._pay_url(order))

    # 4 支付被拒的 200 重渲染：refresh_from_db 后库内已 paid，
    #    联系方式门控须与状态徽章一致，且不被 pay_error 绕过
    def test_pay_error_rerender_gate_matches_status_badge(self):
        order = self._make_order(status='pending_payment')
        self._login(self.buyer)
        Order.objects.filter(pk=order.pk).update(status='paid')

        def stale_lookup(model, *args, **kwargs):
            return order  # 陈旧实例：status 仍为 pending_payment

        with mock.patch('orders.views.get_object_or_404', side_effect=stale_lookup):
            response = self.client.post(self._pay_url(order))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'alert-danger')
        self.assertIn('pay_error', response.context)
        self.assertContains(response, '已支付/待交付')
        self.assertContains(response, '卖家联系方式')
        self.assertContains(response, self.seller.qq)
        self.assertContains(response, self.seller.wechat)
        self.assertNotContains(response, self._pay_url(order))

    # 5 字段未填：中文占位，页面 200、不抛错
    def test_empty_contact_values_show_placeholder(self):
        self.seller.qq = ''
        self.seller.wechat = ''
        self.seller.save(update_fields=['qq', 'wechat'])
        order = self._make_order(status='paid')
        self._login(self.buyer)
        response = self.client.get(self._detail_url(order))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '卖家联系方式')
        self.assertContains(response, '卖家未填写', count=2)

    # 6 他人订单：404 且不泄露联系方式
    def test_other_user_gets_404_without_contact(self):
        order = self._make_order(status='paid')
        self._login(self.other)
        response = self.client.get(self._detail_url(order))
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, self.seller.qq, status_code=404)
        self.assertNotContains(response, self.seller.wechat, status_code=404)
        self.assertNotContains(response, '卖家联系方式', status_code=404)

    # 7 匿名访问：302 到登录页，不泄露联系方式
    def test_anonymous_redirected_to_login(self):
        order = self._make_order(status='paid')
        response = self.client.get(self._detail_url(order))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/login/'))
        self.assertIn('next=', response.url)
        self.assertNotContains(response, self.seller.qq, status_code=302)
        self.assertNotContains(response, self.seller.wechat, status_code=302)

    # 8 下单前页面：即便已有已支付订单，商品详情页/确认页仍无 QQ/微信
    def test_pre_order_pages_never_show_contact(self):
        self._make_order(status='paid')
        self._login(self.buyer)
        urls = (
            reverse('product_detail', args=[self.product.pk]),
            reverse('order_create', kwargs={'product_pk': self.product.pk}),
        )
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'QQ')
                self.assertNotContains(response, '微信')
                self.assertNotContains(response, self.seller.qq)
                self.assertNotContains(response, self.seller.wechat)

    # 9 隐私字面：学号、真实姓名、「学号 (昵称)」形态一律不出现
    def test_no_student_id_or_real_name_leaked(self):
        from accounts.models import VerificationRequest
        VerificationRequest.objects.create(
            user=self.seller, student_id=self.seller.student_id,
            name='卖家真实姓名', status='approved',
        )
        self._login(self.buyer)
        for status in ('pending_payment', 'paid', 'reviewed'):
            with self.subTest(status=status):
                order = self._make_order(status=status)
                response = self.client.get(self._detail_url(order))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, self.seller.student_id)
                self.assertNotContains(response, '卖家真实姓名')
                self.assertNotContains(response, str(self.seller))

    # 10 联系方式值经模板自动转义，不拼接可执行 HTML
    def test_contact_values_are_escaped(self):
        self.seller.qq = '<script>alert(1)</script>'
        self.seller.wechat = 'wx&<b>x</b>'
        self.seller.save(update_fields=['qq', 'wechat'])
        order = self._make_order(status='paid')
        self._login(self.buyer)
        response = self.client.get(self._detail_url(order))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertContains(response, 'wx&amp;&lt;b&gt;x&lt;/b&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertNotContains(response, '<b>x</b>')


class OrderListViewTests(TestCase):
    """4.5 订单列表：覆盖 I/O 矩阵——身份隔离、字段与中文状态、空态、
    登录门控、只读 405/无写入、终态展示、导航与个人中心衔接。"""

    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            student_id='2024401', username='卖家甲', password='test123456',
            qq='88000000001', wechat='wx_seller_4_5',
        )
        cls.buyer = User.objects.create_user(
            student_id='2024402', username='买家甲', password='test123456'
        )
        cls.other = User.objects.create_user(
            student_id='2024403', username='路人乙', password='test123456'
        )
        cls.seller_product = Product.objects.create(
            owner=cls.seller, title='卖家甲的教材', description='x',
            price=Decimal('30.00'), condition='良好', category='教材', status='approved',
        )
        cls.other_product = Product.objects.create(
            owner=cls.other, title='路人乙的商品', description='x',
            price=Decimal('9001.00'), condition='良好', category='教材', status='approved',
        )

    # ---------- helpers ----------
    def _login(self, user):
        self.client.force_login(user)

    def _my_url(self):
        return reverse('my_orders')

    def _sold_url(self):
        return reverse('sold_orders')

    def _make_order(self, buyer, product, status='pending_payment'):
        return Order.objects.create(
            buyer=buyer, product=product, price=product.price, status=status,
        )

    def _snapshot(self):
        return list(Order.objects.values(
            'pk', 'buyer_id', 'product_id', 'price', 'message', 'status',
            'created_at', 'updated_at',
        ).order_by('pk'))

    # ---- 路由：静态列表路径在 <int:pk>/ 之前可达 ----
    def test_static_list_urls(self):
        self.assertEqual(self._my_url(), '/orders/mine/')
        self.assertEqual(self._sold_url(), '/orders/sold/')

    # ---- 买家：仅 buyer=self，字段齐全，他人订单不出现 ----
    def test_my_orders_only_buyer_orders_with_fields(self):
        own1 = self._make_order(self.buyer, self.seller_product)
        own2 = self._make_order(self.buyer, self.other_product)
        other_order = self._make_order(self.other, self.seller_product)
        self._login(self.buyer)

        resp = self.client.get(self._my_url())
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'orders/order_list.html')
        self.assertContains(resp, '我的订单')
        self.assertEqual({o.pk for o in resp.context['orders']}, {own1.pk, own2.pk})
        self.assertTrue(all(o.buyer_id == self.buyer.pk for o in resp.context['orders']))
        for order in (own1, own2):
            self.assertContains(resp, order.product.title)
            self.assertContains(resp, str(order.price))
            self.assertContains(resp, f'#{order.pk}')
            self.assertContains(resp, order.get_status_display())
            self.assertContains(resp, order.created_at.strftime('%Y-%m-%d %H:%M'))
        self.assertNotContains(resp, f'#{other_order.pk}')

    # ---- 卖家：仅 product__owner=self，他人商品订单不出现 ----
    def test_sold_orders_only_own_product_orders(self):
        sold1 = self._make_order(self.buyer, self.seller_product)
        sold2 = self._make_order(self.other, self.seller_product)
        not_mine = self._make_order(self.buyer, self.other_product)
        self._login(self.seller)

        resp = self.client.get(self._sold_url())
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'orders/order_list.html')
        self.assertContains(resp, '售出订单')
        self.assertEqual({o.pk for o in resp.context['orders']}, {sold1.pk, sold2.pk})
        self.assertTrue(
            all(o.product.owner_id == self.seller.pk for o in resp.context['orders'])
        )
        self.assertContains(resp, self.seller_product.title)
        self.assertNotContains(resp, self.other_product.title)
        self.assertNotContains(resp, f'#{not_mine.pk}')

    # ---- 两处空状态 ----
    def test_empty_states_on_both_pages(self):
        self._login(self.other)  # 无买单、无售出单
        for url in (self._my_url(), self._sold_url()):
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200)
                self.assertTrue(resp.context['orders_empty'])
                self.assertEqual(list(resp.context['orders']), [])
                self.assertContains(resp, '暂无订单记录')

    # ---- 登录门控：匿名 GET/POST/HEAD 302 带 next ----
    def test_anonymous_redirected_with_next(self):
        for url in (self._my_url(), self._sold_url()):
            for method in ('get', 'post', 'head'):
                with self.subTest(url=url, method=method):
                    resp = getattr(self.client, method)(url)
                    self.assertEqual(resp.status_code, 302)
                    self.assertEqual(resp.url, f'/login/?next={url}')

    # ---- 只读：405（Allow: GET, HEAD）/ HEAD 200 / 数据库无写入 ----
    def test_read_only_methods_return_405_without_writes(self):
        self._make_order(self.buyer, self.seller_product)
        self._login(self.buyer)
        before = self._snapshot()
        for url in (self._my_url(), self._sold_url()):
            self.assertEqual(self.client.head(url).status_code, 200)
            for method in (self.client.post, self.client.put,
                           self.client.patch, self.client.delete):
                with self.subTest(url=url, method=method):
                    resp = method(url, {'status': 'paid', 'price': '0.01'})
                    self.assertEqual(resp.status_code, 405)
                    self.assertEqual(resp['Allow'], 'GET, HEAD')
        self.assertEqual(self._snapshot(), before)

    # ---- 终态 / 纠纷状态：中文展示且不改动库内状态 ----
    def test_terminal_and_dispute_statuses_display_without_mutation(self):
        statuses = ('reviewed', 'dispute', 'refunded', 'refund_failed')
        orders = {
            s: self._make_order(self.buyer, self.seller_product, status=s)
            for s in statuses
        }
        before = self._snapshot()

        self._login(self.buyer)
        my_page = self.client.get(self._my_url())
        self._login(self.seller)
        sold_page = self.client.get(self._sold_url())
        for resp in (my_page, sold_page):
            self.assertEqual(resp.status_code, 200)
            for s in statuses:
                self.assertContains(resp, orders[s].get_status_display())
                self.assertContains(resp, f'#{orders[s].pk}')
        self.assertEqual(self._snapshot(), before)

    # ---- 排序：创建时间倒序（context 与 HTML 双重断言） ----
    def test_ordered_by_created_at_desc(self):
        o1 = self._make_order(self.buyer, self.seller_product)
        o2 = self._make_order(self.buyer, self.seller_product)
        o3 = self._make_order(self.buyer, self.seller_product)
        now = timezone.now()
        for order, days in ((o1, 5), (o2, 1), (o3, 3)):
            Order.objects.filter(pk=order.pk).update(created_at=now - timedelta(days=days))
            order.refresh_from_db()
        self._login(self.buyer)

        resp = self.client.get(self._my_url())
        expected = [o2.pk, o3.pk, o1.pk]
        self.assertEqual([o.pk for o in resp.context['orders']], expected)
        html = resp.content.decode()
        positions = [html.index(f'#{pk}') for pk in expected]
        self.assertEqual(positions, sorted(positions))

        # 售出订单同样按创建时间倒序：上述三单均在本卖家的商品上。
        self._login(self.seller)
        sold_resp = self.client.get(self._sold_url())
        self.assertEqual([o.pk for o in sold_resp.context['orders']], expected)

    # ---- 链接与隐私：买家链详情、卖家链商品，且不渲染联系方式/操作按钮 ----
    def test_links_and_privacy(self):
        order = self._make_order(self.buyer, self.seller_product)
        self._login(self.buyer)
        my_page = self.client.get(self._my_url())
        self.assertContains(
            my_page, f'href="{reverse("order_detail", args=[order.pk])}"'
        )
        self._login(self.seller)
        sold_page = self.client.get(self._sold_url())
        self.assertContains(
            sold_page,
            f'href="{reverse("product_detail", args=[self.seller_product.pk])}"',
        )
        self.assertNotContains(
            sold_page, f'href="{reverse("order_detail", args=[order.pk])}"'
        )
        for page in (my_page, sold_page):
            self.assertNotContains(page, self.seller.qq)
            self.assertNotContains(page, self.seller.wechat)
            self.assertNotContains(page, '确认收货')
            self.assertNotContains(page, '模拟支付')

    # ---- 个人中心摘要 + 顶部导航入口 ----
    def test_profile_summary_and_nav_entry(self):
        # 锚定按钮自身的 HTML（含专属 class 与「查看全部」文案），避免仅凭
        # base.html 导航里同样存在的 /orders/mine/ href 造成假阳性。
        view_all_button = (
            f'<a href="{self._my_url()}" '
            'class="btn btn-outline-secondary btn-sm mt-3">查看全部</a>'
        )
        self._login(self.buyer)
        empty = self.client.get(reverse('profile'))
        self.assertTrue(empty.context['my_orders_empty'])
        self.assertContains(empty, '暂无订单记录')
        self.assertContains(empty, view_all_button)

        order = self._make_order(self.buyer, self.seller_product, status='paid')
        resp = self.client.get(reverse('profile'))
        self.assertFalse(resp.context['my_orders_empty'])
        self.assertContains(resp, self.seller_product.title)
        self.assertContains(resp, order.get_status_display())
        self.assertContains(resp, view_all_button)
        self.assertTrue(all(o.buyer_id == self.buyer.pk for o in resp.context['my_orders']))

        home = self.client.get(reverse('home'))
        self.assertContains(home, f'href="{self._my_url()}"')
        self.client.logout()
        self.assertNotContains(self.client.get(reverse('home')),
                               f'href="{self._my_url()}"')

    # ---- 个人中心摘要：buyer 隔离（改 filter(buyer=...) 为 all() 必须失败） ----
    def test_profile_summary_isolates_other_buyers_orders(self):
        mine = self._make_order(self.buyer, self.seller_product)
        self._make_order(self.other, self.other_product)
        self._login(self.buyer)

        resp = self.client.get(reverse('profile'))
        self.assertEqual({o.pk for o in resp.context['my_orders']}, {mine.pk})
        self.assertContains(resp, self.seller_product.title)
        self.assertNotContains(resp, self.other_product.title)

    # ---- 个人中心摘要仅最近若干条：区分 created_at，且上限跟随生产常量 ----
    def test_profile_summary_is_limited_to_recent(self):
        now = timezone.now()
        recent, oldest = [], []
        for i in range(7):
            product = Product.objects.create(
                owner=self.seller, title=f'摘要专用商品{i}', description='x',
                price=Decimal('10.00'), condition='良好', category='教材',
                status='approved',
            )
            order = self._make_order(self.buyer, product)
            Order.objects.filter(pk=order.pk).update(
                created_at=now - timedelta(days=7 - i)
            )
            order.refresh_from_db()
            (recent if i >= 2 else oldest).append(order)
        self._login(self.buyer)

        resp = self.client.get(reverse('profile'))
        summary = resp.context['my_orders']
        self.assertEqual(len(summary), PROFILE_ORDERS_SUMMARY_LIMIT)
        self.assertEqual({o.pk for o in summary}, {o.pk for o in recent})
        for order in recent:
            self.assertContains(resp, order.product.title)
        for order in oldest:
            self.assertNotContains(resp, order.product.title)

    # ---- 他人订单详情仍 404（既有行为，本故事保持不变） ----
    def test_other_user_order_detail_still_404(self):
        order = self._make_order(self.buyer, self.seller_product)
        self._login(self.other)
        self.assertEqual(
            self.client.get(reverse('order_detail', args=[order.pk])).status_code, 404
        )


class OrderReviewTests(TestCase):
    """4.7 互评：覆盖 I/O 矩阵——先后评、单方不流转、状态不符、重复、越权、未登录。"""

    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            student_id='2025201', username='卖家', password='test123456'
        )
        cls.buyer = User.objects.create_user(
            student_id='2025202', username='买家', password='test123456'
        )
        cls.other = User.objects.create_user(
            student_id='2025203', username='路人', password='test123456'
        )
        cls.product = Product.objects.create(
            owner=cls.seller, title='线性代数教材', description='x',
            price=Decimal('30.00'), condition='良好', category='教材', status='approved',
        )

    # ---------- helpers ----------
    def _make_order(self, status='completed'):
        return Order.objects.create(
            buyer=self.buyer, product=self.product,
            price=self.product.price, status=status,
        )

    def _review_url(self, order):
        return reverse('order_review', kwargs={'pk': order.pk})

    def _login(self, user):
        self.client.force_login(user)

    def _add_review(self, order, user, content='评价内容'):
        return Review.objects.create(order=order, reviewer=user, content=content)

    # 1 买家先评：落评价、推导身份、订单仍「已完成」
    def test_buyer_review_first_keeps_order_completed(self):
        order = self._make_order()
        self._login(self.buyer)
        response = self.client.post(self._review_url(order), {'content': '书很新'})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self._review_url(order))
        order.refresh_from_db()
        self.assertEqual(order.status, 'completed')
        review = Review.objects.get(order=order)
        self.assertEqual(review.reviewer, self.buyer)
        self.assertEqual(review.reviewee, self.seller)
        self.assertTrue(review.reviewer_is_buyer)
        self.assertEqual(review.content, '书很新')

    # 2 卖家后评闭环：第二条经 mark_reviewed() → reviewed
    def test_seller_second_review_closes_loop(self):
        order = self._make_order()
        self._add_review(order, self.buyer, '买家评价')
        self._login(self.seller)
        response = self.client.post(self._review_url(order), {'content': '买家很守时'})

        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, 'reviewed')
        self.assertEqual(order.reviews.count(), 2)
        seller_review = Review.objects.get(order=order, reviewer=self.seller)
        self.assertFalse(seller_review.reviewer_is_buyer)
        self.assertEqual(seller_review.reviewee, self.buyer)

    # 3 顺序对称：卖家先评 / 买家后评同样在第二条闭环
    def test_seller_first_then_buyer_symmetric(self):
        order = self._make_order()
        self._add_review(order, self.seller, '卖家先评')
        order.refresh_from_db()
        self.assertEqual(order.status, 'completed')

        self._login(self.buyer)
        response = self.client.post(self._review_url(order), {'content': '买家后评'})
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, 'reviewed')
        self.assertEqual(order.reviews.count(), 2)

    # 4 单方未齐：状态保持「已完成」，页面提示等待对方评价
    def test_single_review_waits_and_shows_hint(self):
        order = self._make_order()
        self._add_review(order, self.buyer, '先评')
        self._login(self.buyer)
        response = self.client.get(self._review_url(order))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '等待对方评价')
        self.assertContains(response, '你已评价')
        self.assertContains(response, order.get_status_display())
        order.refresh_from_db()
        self.assertEqual(order.status, 'completed')

    # 5 状态不符：拒绝、不落评价、不改状态
    def test_invalid_status_rejected(self):
        self._login(self.buyer)
        for status in ('pending_payment', 'paid', 'received', 'dispute', 'reviewed'):
            with self.subTest(status=status):
                order = self._make_order(status=status)
                before = Review.objects.count()
                response = self.client.post(self._review_url(order), {'content': '评价'})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'alert-danger')
                self.assertContains(response, REVIEW_STATUS_ERROR)
                self.assertEqual(Review.objects.count(), before)
                order.refresh_from_db()
                self.assertEqual(order.status, status)

    # 6 重复提交：拒绝且不产生第二条
    def test_duplicate_review_rejected(self):
        order = self._make_order()
        self._add_review(order, self.buyer, '第一条')
        self._login(self.buyer)
        response = self.client.post(self._review_url(order), {'content': '第二条'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, REVIEW_DUPLICATE_ERROR)
        self.assertEqual(order.reviews.filter(reviewer=self.buyer).count(), 1)
        order.refresh_from_db()
        self.assertEqual(order.status, 'completed')

    # 7 越权：非当事人 GET/POST 一律 404
    def test_other_user_404_on_get_and_post(self):
        order = self._make_order()
        self._login(self.other)
        for method in ('get', 'post'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    self._review_url(order), {'content': 'x'}
                )
                self.assertEqual(response.status_code, 404)
        self.assertEqual(Review.objects.count(), 0)

    # 8 未登录：GET/POST 302 跳登录页并带 next
    def test_anonymous_redirected_to_login(self):
        order = self._make_order()
        for method in ('get', 'post'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    self._review_url(order), {'content': 'x'}
                )
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith('/login/'))
                self.assertIn('next=', response.url)
        self.assertEqual(Review.objects.count(), 0)

    # 9 空白评价被拒（含纯空白）
    def test_empty_content_rejected(self):
        order = self._make_order()
        self._login(self.buyer)
        for content in ('', '   '):
            with self.subTest(content=repr(content)):
                response = self.client.post(self._review_url(order), {'content': content})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, '评价内容不能为空')
                self.assertEqual(Review.objects.count(), 0)

    # 10 GET 展示表单、评价对象与状态
    def test_get_shows_form_reviewee_and_status(self):
        order = self._make_order()
        self._login(self.buyer)
        response = self.client.get(self._review_url(order))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'orders/order_review.html')
        self.assertContains(response, '订单互评')
        self.assertContains(response, self.product.title)
        self.assertContains(response, self.seller.username)
        self.assertContains(response, 'name="content"')
        self.assertContains(response, '提交评价')
        self.assertEqual(list(ReviewForm().fields), ['content'])

    # 11 伪造 reviewer/status 字段无效：身份完全由登录用户推导
    def test_forged_reviewer_fields_ignored(self):
        order = self._make_order()
        self._login(self.buyer)
        response = self.client.post(self._review_url(order), {
            'content': '真实评价',
            'reviewer': self.other.pk,
            'order': self._make_order().pk,
            'status': 'reviewed',
        })

        self.assertEqual(response.status_code, 302)
        review = Review.objects.get()
        self.assertEqual(review.reviewer, self.buyer)
        self.assertEqual(review.order, order)
        self.assertEqual(review.content, '真实评价')
        order.refresh_from_db()
        self.assertEqual(order.status, 'completed')

    # 12 不存在的订单 404
    def test_nonexistent_order_404(self):
        self._login(self.buyer)
        url = reverse('order_review', kwargs={'pk': 999999})
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {'content': 'x'}).status_code, 404)

    # 13 PUT/DELETE → 405
    def test_unsafe_methods_405(self):
        order = self._make_order()
        self._login(self.buyer)
        for method in ('put', 'delete'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self._review_url(order))
                self.assertEqual(response.status_code, 405)

    # 14 详情页与两个订单列表均有评价入口
    def test_entry_links_on_detail_and_both_lists(self):
        order = self._make_order()
        url = self._review_url(order)

        self._login(self.buyer)
        self.assertContains(
            self.client.get(reverse('order_detail', args=[order.pk])), url
        )
        self.assertContains(self.client.get(reverse('my_orders')), url)

        self._login(self.seller)
        self.assertContains(self.client.get(reverse('sold_orders')), url)

    # 15 个人中心「我的评价」只展示我收到的评价
    def test_profile_shows_received_reviews_only(self):
        order = self._make_order()
        self._add_review(order, self.buyer, '卖家收到的评价')
        self._add_review(order, self.seller, '买家收到的评价')

        self._login(self.seller)
        seller_profile = self.client.get(reverse('profile'))
        self.assertContains(seller_profile, '卖家收到的评价')
        self.assertNotContains(seller_profile, '买家收到的评价')
        self.assertEqual(len(seller_profile.context['my_reviews']), 1)

        self._login(self.buyer)
        buyer_profile = self.client.get(reverse('profile'))
        self.assertContains(buyer_profile, '买家收到的评价')
        self.assertNotContains(buyer_profile, '卖家收到的评价')
        self.assertEqual(len(buyer_profile.context['my_reviews']), 1)

        self._login(self.other)
        other_profile = self.client.get(reverse('profile'))
        self.assertTrue(other_profile.context['my_reviews_empty'])

    # 16 数据库唯一约束兜底：同一订单同一当事人至多一条
    def test_unique_constraint_per_order_and_reviewer(self):
        order = self._make_order()
        self._add_review(order, self.buyer)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._add_review(order, self.buyer)

    # 17 双方齐备：GET 展示闭环横幅与对方评价正文
    def test_both_reviewed_get_shows_banner_and_other_review(self):
        order = self._make_order()
        self._add_review(order, self.buyer, '买家评价正文')
        self._add_review(order, self.seller, '卖家评价正文')

        self._login(self.buyer)
        response = self.client.get(self._review_url(order))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '双方已完成互评')
        self.assertContains(response, '卖家评价正文')


class RefundRequestModelTests(TestCase):
    """4.8 RefundRequest：落库字段、关系与级联，供后续裁决读取。"""

    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            student_id='2026201', username='卖家', password='test123456'
        )
        cls.buyer = User.objects.create_user(
            student_id='2026202', username='买家', password='test123456'
        )
        cls.product = Product.objects.create(
            owner=cls.seller, title='线性代数教材', description='x',
            price=Decimal('30.00'), condition='良好', category='教材', status='approved',
        )
        cls.order = Order.objects.create(
            buyer=cls.buyer, product=cls.product,
            price=cls.product.price, status='paid',
        )

    def test_create_persists_reason_order_and_relation(self):
        refund = RefundRequest.objects.create(order=self.order, reason='商品与描述不符')

        refund.refresh_from_db()
        self.assertEqual(refund.reason, '商品与描述不符')
        self.assertEqual(refund.order, self.order)
        self.assertIsNotNone(refund.created_at)
        self.assertEqual(list(self.order.refund_requests.all()), [refund])
        self.assertIn('退款请求', str(refund))

    def test_order_cascade_deletes_refund_requests(self):
        refund = RefundRequest.objects.create(order=self.order, reason='货不对板')

        self.order.delete()

        self.assertFalse(RefundRequest.objects.filter(pk=refund.pk).exists())


class OrderRefundViewTests(TestCase):
    """4.8 退款申请：HTTP 层覆盖 I/O 矩阵全部场景。"""

    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            student_id='2027201', username='卖家', password='test123456'
        )
        cls.buyer = User.objects.create_user(
            student_id='2027202', username='买家', password='test123456'
        )
        cls.other = User.objects.create_user(
            student_id='2027203', username='路人', password='test123456'
        )
        cls.product = Product.objects.create(
            owner=cls.seller, title='线性代数教材', description='x',
            price=Decimal('30.00'), condition='良好', category='教材', status='approved',
        )

    # ---------- helpers ----------
    def _make_order(self, status='paid'):
        return Order.objects.create(
            buyer=self.buyer, product=self.product,
            price=self.product.price, status=status,
        )

    def _refund_url(self, order):
        return reverse('order_refund', kwargs={'pk': order.pk})

    def _detail_url(self, order):
        return reverse('order_detail', kwargs={'pk': order.pk})

    def _login(self, user):
        self.client.login(username=user.student_id, password='test123456')

    # 1 正常退款：302 回详情、status=dispute、原因与订单落库
    def test_refund_success_transitions_persists_reason_and_redirects(self):
        order = self._make_order()
        self._login(self.buyer)

        response = self.client.post(self._refund_url(order), {'reason': '货不对板'})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self._detail_url(order))
        order.refresh_from_db()
        self.assertEqual(order.status, 'dispute')
        refunds = RefundRequest.objects.filter(order=order)
        self.assertEqual(refunds.count(), 1)
        self.assertEqual(refunds.get().reason, '货不对板')

        detail = self.client.get(self._detail_url(order))
        self.assertContains(detail, '纠纷')
        self.assertNotContains(detail, self._refund_url(order))

    # 2 原因必填：空/纯空白 → 200 表单错误，状态与记录不变
    def test_empty_or_blank_reason_rejected(self):
        order = self._make_order()
        self._login(self.buyer)
        for reason in ('', '   ', '\t\n'):
            with self.subTest(reason=repr(reason)):
                response = self.client.post(self._refund_url(order), {'reason': reason})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, '退款原因不能为空')
                self.assertEqual(RefundRequest.objects.count(), 0)
                order.refresh_from_db()
                self.assertEqual(order.status, 'paid')

    # 3 入口可见性：仅 paid 详情显示退款链接
    def test_refund_link_only_shown_when_paid(self):
        self._login(self.buyer)
        paid = self._make_order(status='paid')
        detail = self.client.get(self._detail_url(paid))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, self._refund_url(paid))
        self.assertContains(detail, '申请退款')

        for status in ('pending_payment', 'received', 'completed', 'reviewed',
                       'dispute', 'refunded', 'refund_failed'):
            order = self._make_order(status=status)
            with self.subTest(status=status):
                detail = self.client.get(self._detail_url(order))
                self.assertEqual(detail.status_code, 200)
                self.assertNotContains(detail, self._refund_url(order))
                self.assertContains(detail, order.get_status_display())

    # 4 独立页 GET：paid 展示含原因 textarea 的空表单
    def test_get_shows_form_on_paid_order(self):
        order = self._make_order()
        self._login(self.buyer)

        response = self.client.get(self._refund_url(order))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'orders/order_refund.html')
        self.assertContains(response, '申请退款')
        self.assertContains(response, self.product.title)
        self.assertContains(response, 'name="reason"')
        self.assertContains(response, '退款原因')
        self.assertContains(response, '提交退款申请')
        self.assertIn('form', response.context)
        self.assertEqual(list(RefundRequestForm().fields), ['reason'])
        self.assertTrue(response.context['can_refund'])

    # 5 GET 非 paid：200 仅拒绝提示，无可提交表单
    def test_get_non_paid_shows_rejection_without_form(self):
        self._login(self.buyer)
        for status in ('pending_payment', 'received', 'completed', 'reviewed',
                       'dispute', 'refunded', 'refund_failed'):
            order = self._make_order(status=status)
            with self.subTest(status=status):
                response = self.client.get(self._refund_url(order))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, REFUND_STATUS_ERROR)
                self.assertContains(response, order.get_status_display())
                self.assertNotContains(response, 'name="reason"')
                self.assertFalse(response.context['can_refund'])

    # 6 非安全方法：PUT/DELETE → 405，状态不变
    def test_unsafe_methods_405(self):
        order = self._make_order()
        self._login(self.buyer)
        for method in ('put', 'delete'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self._refund_url(order))
                self.assertEqual(response.status_code, 405)
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')
        self.assertEqual(RefundRequest.objects.count(), 0)

    # 7 非 paid 提交：200 中文拒绝、状态与记录不变
    def test_non_paid_status_rejected(self):
        self._login(self.buyer)
        for status in ('pending_payment', 'received', 'completed', 'reviewed',
                       'dispute', 'refunded', 'refund_failed'):
            order = self._make_order(status=status)
            with self.subTest(status=status):
                response = self.client.post(self._refund_url(order), {'reason': '货不对板'})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'alert-danger')
                self.assertContains(response, REFUND_STATUS_ERROR)
                order.refresh_from_db()
                self.assertEqual(order.status, status)
        self.assertEqual(RefundRequest.objects.count(), 0)

    # 8 未登录：GET/POST 302 跳登录页并带 next
    def test_anonymous_redirected_to_login(self):
        order = self._make_order()
        for method in ('get', 'post'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    self._refund_url(order), {'reason': '货不对板'}
                )
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith('/login/'))
                self.assertIn('next=', response.url)
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')
        self.assertEqual(RefundRequest.objects.count(), 0)

    # 9 越权/不存在：非 buyer 与不存在 pk 一律 404
    def test_other_user_and_nonexistent_order_404(self):
        order = self._make_order()
        self._login(self.other)
        for method in ('get', 'post'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    self._refund_url(order), {'reason': '货不对板'}
                )
                self.assertEqual(response.status_code, 404)
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')
        self.assertEqual(RefundRequest.objects.count(), 0)

        self._login(self.buyer)
        url = reverse('order_refund', kwargs={'pk': 999999})
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {'reason': 'x'}).status_code, 404)

    # 10 伪造字段：status/buyer/order 被忽略，仅依状态机与登录用户流转
    def test_forged_post_fields_ignored(self):
        order = self._make_order()
        other_order = self._make_order()
        self._login(self.buyer)

        response = self.client.post(self._refund_url(order), {
            'reason': '真实原因',
            'status': 'refunded',
            'buyer': self.other.pk,
            'order': other_order.pk,
        })

        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, 'dispute')
        self.assertEqual(order.buyer, self.buyer)
        refund = RefundRequest.objects.get()
        self.assertEqual(refund.order, order)
        self.assertEqual(refund.reason, '真实原因')
        self.assertEqual(RefundRequest.objects.filter(order=other_order).count(), 0)

    # 11 连续两次提交：仅一次成功，第二次 200 拒绝且无第二条记录
    def test_double_submit_only_once(self):
        order = self._make_order()
        self._login(self.buyer)

        first = self.client.post(self._refund_url(order), {'reason': '货不对板'})
        self.assertEqual(first.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, 'dispute')

        second = self.client.post(self._refund_url(order), {'reason': '再申请一次'})
        self.assertEqual(second.status_code, 200)
        self.assertContains(second, REFUND_STATUS_ERROR)
        refunds = RefundRequest.objects.filter(order=order)
        self.assertEqual(refunds.count(), 1)
        self.assertEqual(refunds.get().reason, '货不对板')
        order.refresh_from_db()
        self.assertEqual(order.status, 'dispute')

    # 12 并发/陈旧实例：库内已被推进，条件更新挡住二次流转，事务回滚不留原因
    def test_concurrent_stale_instance_rejected_visibly(self):
        order = self._make_order()
        self._login(self.buyer)
        # 模拟并发请求先把库内状态推进到 dispute（不影响内存中 order 的 status）
        Order.objects.filter(pk=order.pk).update(status='dispute')

        def stale_lookup(model, *args, **kwargs):
            return order  # 陈旧实例：status 仍为 paid

        with mock.patch('orders.views.get_object_or_404', side_effect=stale_lookup):
            response = self.client.post(self._refund_url(order), {'reason': '货不对板'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'alert-danger')
        self.assertContains(response, REFUND_STATUS_ERROR)
        self.assertContains(response, '纠纷')  # 徽章反映库内真实状态
        self.assertEqual(Order.objects.get(pk=order.pk).status, 'dispute')
        self.assertEqual(RefundRequest.objects.filter(order=order).count(), 0)
