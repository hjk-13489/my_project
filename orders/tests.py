from decimal import Decimal
from unittest import mock

from django.test import TestCase

from accounts.models import User
from listings.models import Product
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
