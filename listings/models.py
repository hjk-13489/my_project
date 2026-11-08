from django.conf import settings
from django.db import models


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

    class Meta:
        verbose_name = '商品'
        verbose_name_plural = '商品'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.title}（{self.get_status_display()}）'


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
