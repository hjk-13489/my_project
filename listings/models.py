from django.conf import settings
from django.db import models


class InvalidTransition(Exception):
    """商品状态非法流转：显式拒绝，保持原状态且不落库。"""


class ProductQuerySet(models.QuerySet):
    """商品查询集：对外可见性的唯一定义。"""

    def visible(self):
        """返回且仅返回已上架（approved）商品，可继续链式 filter() 等操作。"""
        return self.filter(status='approved')


class Product(models.Model):
    """商品：卖家发布的闲置物品，提交后默认待审核（pending）。"""

    CATEGORY_CHOICES = [
        ('教材', '教材'),
        ('日用品', '日用品'),
        ('电子数码', '电子数码'),
        ('其他', '其他'),
    ]
    CONDITION_CHOICES = [
        ('全新', '全新'),
        ('良好', '良好'),
        ('中等', '中等'),
    ]
    STATUS_CHOICES = [
        ('pending', '待审核'),
        ('approved', '已上架'),
        ('rejected', '已驳回'),
        ('offline', '已下架'),
    ]
    # 状态流转唯一定义：仅 pending 可流转到 approved / rejected；
    # approved → offline（5.2）、rejected → pending（2.3）留给后续故事。
    ALLOWED_TRANSITIONS = {
        'pending': ('approved', 'rejected'),
        'approved': (),
        'rejected': (),
        'offline': (),
    }

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='products',
        verbose_name='卖家',
    )
    title = models.CharField(max_length=100, verbose_name='标题')
    description = models.TextField(verbose_name='描述')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='价格')
    condition = models.CharField(max_length=8, choices=CONDITION_CHOICES, verbose_name='成色')
    category = models.CharField(max_length=8, choices=CATEGORY_CHOICES, verbose_name='分类')
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default='pending', verbose_name='状态'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    # 只追加 visible() 等方法，基础查询集不过滤，admin / 卖家本人 / 既有代码不受影响。
    objects = ProductQuerySet.as_manager()

    class Meta:
        verbose_name = '商品'
        verbose_name_plural = '商品'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.title}（{self.get_status_display()}）'

    # ---------- 状态流转（模型层唯一入口）----------
    def approve(self):
        """审核通过：pending → approved。"""
        self._transition('approved')

    def reject(self):
        """审核驳回：pending → rejected。"""
        self._transition('rejected')

    def _transition(self, target):
        """执行合法转移并持久化；非法转移抛 InvalidTransition，不改动状态、不落库。"""
        allowed = self.ALLOWED_TRANSITIONS.get(self.status, ())
        if target not in allowed:
            target_display = dict(self.STATUS_CHOICES).get(target, target)
            raise InvalidTransition(
                f'非法状态流转：当前为「{self.get_status_display()}」，'
                f'不能流转到「{target_display}」'
            )
        self.status = target
        self.save(update_fields=['status', 'updated_at'])


class ProductImage(models.Model):
    """商品图片：独立实体，每个商品 1–5 张。"""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='商品',
    )
    image = models.ImageField(upload_to='products/', verbose_name='图片')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='上传时间')

    class Meta:
        verbose_name = '商品图片'
        verbose_name_plural = '商品图片'

    def __str__(self):
        return f'{self.product.title} - {self.image.name}'
