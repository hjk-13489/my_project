from django.contrib import admin
from .models import Product, ProductImage

# 仅注册模型供人工验收查看 pending 数据；审核流转 action 属 story 5.1，本故事不实现。
admin.site.register(Product)
admin.site.register(ProductImage)
