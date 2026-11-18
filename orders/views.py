from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods, require_safe

from listings.models import Product

from .forms import OrderCreateForm
from .models import InvalidTransition, Order

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


# 模拟支付：仅 POST、仅 buyer 本人。@login_required 外层使匿名请求先跳登录页
# 而非落到 405；@require_POST 内层把 GET/PUT/DELETE 一律挡成 405。
@login_required
@require_POST
def order_pay(request, pk):
    """模拟支付：在单个事务内经 Order.pay() 完成 pending_payment → paid。

    取订单与 pay() 置于同一事务，使读取与流转构成不可分割的动作；并发重复
    提交由 _transition() 的条件更新兜底。非法/重复/陈旧实例流转抛
    InvalidTransition，以 200 重渲染详情页并给出 alert-danger 中文拒绝提示；
    成功则 PRG 回详情页，由状态徽章呈现结果。
    """
    try:
        with transaction.atomic():
            order = get_object_or_404(Order, pk=pk, buyer=request.user)
            order.pay()
    except InvalidTransition:
        # _transition() 在「条件更新命中 0 行」时抛错且未改写 self.status；
        # 并发/陈旧实例被拒时库内状态可能已被推进，重读后再渲染，
        # 避免状态徽章仍显示陈旧的「待支付」。
        order.refresh_from_db()
        return render(request, 'orders/order_detail.html',
                      {'order': order,
                       'pay_error': '支付被拒绝：订单当前状态不允许支付，请勿重复提交；当前状态以上方状态徽章为准'})
    return redirect('order_detail', pk=pk)


# 4.6 确认收货：仅 POST、仅 buyer 本人。沿用 order_pay 的 decorator 组合与
# 事务范式；状态流转只经 Order.confirm_receipt()（paid → received → completed），
# received 为事务中间态，不对外可见。
@login_required
@require_POST
def order_confirm_receipt(request, pk):
    """确认收货：在单个事务内经 Order.confirm_receipt() 完成两跳流转。

    取订单与 confirm_receipt() 置于同一事务；非法/重复/陈旧实例流转抛
    InvalidTransition，以 200 重渲染详情页并给出 alert-danger 中文拒绝提示
    （键名 receipt_error，与 pay_error 互不混用）；成功则 PRG 回详情页。
    """
    try:
        with transaction.atomic():
            order = get_object_or_404(Order, pk=pk, buyer=request.user)
            order.confirm_receipt()
    except InvalidTransition:
        # 并发/陈旧实例被拒时库内状态可能已被推进，重读后再渲染，
        # 使状态徽章反映库内真实状态，而不是被拒绝的内存状态。
        order.refresh_from_db()
        return render(request, 'orders/order_detail.html',
                      {'order': order,
                       'receipt_error': '收货被拒绝：订单当前状态不允许确认收货，请勿重复提交；当前状态以上方状态徽章为准'})
    return redirect('order_detail', pk=pk)


# 4.5 订单列表：沿用 2.4 的只读列表范式（@login_required 外层 + @require_safe 内层、
# 服务端强制过滤、list() 求值、创建时间倒序、不分页）。两者共用同一模板，以 mode
# 区分身份：买家列表项链到 order_detail（仅 buyer 可见），卖家列表项链到公开的
# product_detail，避免卖家点击后落入只认 buyer 的详情而 404。
@login_required
@require_safe
def my_orders_view(request):
    """我的订单：按 buyer=request.user 只读呈现本人全部订单（含各终态）。"""
    orders = list(Order.objects.filter(buyer=request.user).select_related('product'))
    return render(request, 'orders/order_list.html', {
        'orders': orders,
        'orders_empty': not orders,
        'mode': 'buyer',
        'list_title': '我的订单',
    })


@login_required
@require_safe
def sold_orders_view(request):
    """售出订单：按 product__owner=request.user 只读呈现本人商品的全部订单。"""
    orders = list(
        Order.objects.filter(product__owner=request.user).select_related('product')
    )
    return render(request, 'orders/order_list.html', {
        'orders': orders,
        'orders_empty': not orders,
        'mode': 'seller',
        'list_title': '售出订单',
    })
