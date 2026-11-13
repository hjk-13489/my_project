from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class InvalidTransition(Exception):
    """订单状态非法流转：显式拒绝，保持原状态且不落库。"""


class Order(models.Model):
    """订单：买家对某件商品的交易凭证，初始状态为待支付。"""

    STATUS_CHOICES = [
        ('pending_payment', '待支付'),
        ('paid', '已支付/待交付'),
        ('received', '已确认收货'),
        ('completed', '已完成'),
        ('reviewed', '已互评'),
        ('dispute', '纠纷'),
        ('refunded', '退款成功'),
        ('refund_failed', '退款失败'),
    ]
    # 状态流转唯一定义：正常路径 pending_payment → paid → received → completed → reviewed，
    # 退款分支 paid → dispute → refunded / refund_failed。
    ALLOWED_TRANSITIONS = {
        'pending_payment': ('paid',),
        'paid': ('received', 'dispute'),
        'received': ('completed',),
        'completed': ('reviewed',),
        'reviewed': (),
        'dispute': ('refunded', 'refund_failed'),
        'refunded': (),
        'refund_failed': (),
    }

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders',
        verbose_name='买家',
    )
    # 商品被删除不应抹掉历史订单：订单是交易凭证，故用 PROTECT。
    product = models.ForeignKey(
        'listings.Product',
        on_delete=models.PROTECT,
        related_name='orders',
        verbose_name='商品',
    )
    # 下单时的价格快照，商品后续改价不影响历史订单。
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='成交价格')
    message = models.TextField(blank=True, verbose_name='留言')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending_payment', verbose_name='状态'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '订单'
        verbose_name_plural = '订单'
        ordering = ('-created_at',)

    def __str__(self):
        return f'订单 #{self.pk}（{self.get_status_display()}）'

    # ---------- 状态流转（模型层唯一入口）----------
    def pay(self):
        """模拟支付：pending_payment → paid。"""
        self._transition('paid')

    def confirm_receipt(self):
        """确认收货：paid → received → completed，两跳在同一事务内完成。

        FR-22 要求收货后由系统随即自动标记已完成；任一步失败整体回滚。
        """
        with transaction.atomic():
            self._transition('received')
            self._transition('completed')

    def request_refund(self):
        """发起退款：paid → dispute，等待管理员裁决。

        原因字段属于 4.8 的 RefundRequest 实体，本方法只做状态流转。
        """
        self._transition('dispute')

    def resolve_refund(self, agree):
        """管理员裁决：dispute → refunded（同意）/ refund_failed（拒绝）。

        agree 必须是布尔值：'false' / '0' 等字符串若按真值处理，会把「拒绝」
        误记成「退款成功」，故非布尔入参一律拒绝。
        """
        if not isinstance(agree, bool):
            raise ValueError('裁决结果必须是布尔值：True 表示同意退款，False 表示拒绝退款')
        self._transition('refunded' if agree else 'refund_failed')

    def mark_reviewed(self):
        """双方互评完成：completed → reviewed，供 4.7 调用。"""
        self._transition('reviewed')

    def _transition(self, target):
        """执行合法转移并持久化；非法转移抛 InvalidTransition，不改动状态、不落库。

        以「库内状态 = 本实例内存状态」为条件做原子更新：陈旧实例不会覆盖
        已被其他实例推进的状态，条件命中 0 行同样视为非法流转。
        """
        allowed = self.ALLOWED_TRANSITIONS.get(self.status, ())
        target_display = dict(self.STATUS_CHOICES).get(target, target)
        if target not in allowed:
            raise InvalidTransition(
                f'非法状态流转：当前为「{self.get_status_display()}」，'
                f'不能流转到「{target_display}」'
            )
        now = timezone.now()
        with transaction.atomic():
            updated = Order.objects.filter(pk=self.pk, status=self.status).update(
                status=target, updated_at=now
            )
            if not updated:
                raise InvalidTransition(
                    f'非法状态流转：订单当前状态已被其他操作变更，'
                    f'不能流转到「{target_display}」'
                )
        self.status = target
        self.updated_at = now
