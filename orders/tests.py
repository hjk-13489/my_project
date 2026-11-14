from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from listings.models import Product
from orders.forms import OrderCreateForm
from orders.models import InvalidTransition, Order


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
                self.assertContains(response, '支付未成功：订单当前状态不允许支付，请刷新页面确认后重试')
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
        self.assertContains(second, '支付未成功：订单当前状态不允许支付，请刷新页面确认后重试')
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
        self.assertContains(response, '支付未成功：订单当前状态不允许支付，请刷新页面确认后重试')
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
