from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe

from listings.models import Product

from .forms import OrderCreateForm
from .models import Order

# 已收尾状态：这些状态不再占用「同一买家 + 同一商品」的下单名额。
CLOSED_STATUSES = ('completed', 'reviewed', 'refunded', 'refund_failed')


# @login_required 外层：未登录 GET/POST 优先 302 到登录页（带 next）。
# 内层显式放行 GET/HEAD/POST，其余方法 405；与 listings/views.py 既有组合一致。
@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def order_create(request, product_pk):
    """订单确认/创建：GET 展示可下单商品，POST 在同一事务内做两条约束校验并建单。"""
    # 可下单对象只能经 visible() 取得：非 approved / 不存在一律 404。
    product = get_object_or_404(
        Product.objects.visible().select_related('owner'),
        pk=product_pk,
    )

    if request.method == 'POST':
        form = OrderCreateForm(request.POST)
        if form.is_valid():
            created = None
            # D1 两条校验与建单处于同一事务，缩小重复提交的竞态窗口。
            with transaction.atomic():
                if request.user == product.owner:
                    form.add_error(None, '不能购买自己发布的商品')
                elif Order.objects.filter(
                    buyer=request.user, product=product
                ).exclude(status__in=CLOSED_STATUSES).exists():
                    form.add_error(None, '该商品已有进行中的订单')
                else:
                    created = Order.objects.create(
                        buyer=request.user,
                        product=product,
                        price=product.price,
                        message=form.cleaned_data['message'],
                    )
            if created is not None:
                return redirect('order_detail', pk=created.pk)
    else:
        form = OrderCreateForm()

    return render(request, 'orders/order_confirm.html', {
        'product': product,
        'form': form,
    })


# @login_required 外层 + @require_safe 内层：仅本人可读、仅 GET/HEAD。
# 按 buyer 过滤，他人订单一律 404；卖家侧「售出订单」属 4.5，不在本次范围。
@login_required
@require_safe
def order_detail(request, pk):
    """最小订单详情页：仅 buyer 本人可见，展示商品/价格/留言/当前状态。"""
    order = get_object_or_404(Order, pk=pk, buyer=request.user)
    return render(request, 'orders/order_detail.html', {'order': order})
