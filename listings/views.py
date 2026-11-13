from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_http_methods, require_safe

from .forms import ProductForm, validate_images
from .models import Product, ProductImage, RejectionNotice


# @login_required 置于外层：未登录访客优先 302 到登录页（带 next）。
# 内层显式放行 GET/HEAD/POST：POST 需绑定 request.FILES，且 HEAD 不被误拒为 405。
@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def publish_view(request):
    """发布商品页：登录 + 学号认证双门控，提交后以 pending 原子落库并留在成功态。"""

    # 已登录但未认证：200 提示页，表单处理前拦截，不创建记录、不写 media/。
    if not request.user.is_verified:
        return render(request, 'listings/publish.html', {'needs_verification': True})

    if request.method == 'POST':
        form = ProductForm(request.POST)
        # 先触发表单校验以建立 form._errors，图片错误才能用 add_error 汇入同一错误区。
        form_valid = form.is_valid()
        images = request.FILES.getlist('images')
        image_errors = validate_images(images)
        for message in image_errors:
            form.add_error(None, message)

        if form_valid and not image_errors:
            # 商品与 1–5 张图片同成同败；owner/status 由服务端强制写入，不接受请求传值。
            with transaction.atomic():
                product = form.save(commit=False)
                product.owner = request.user
                product.status = 'pending'
                product.save()
                for image_file in images:
                    ProductImage.objects.create(product=product, image=image_file)
            return render(request, 'listings/publish.html', {'submitted': True})
    else:
        form = ProductForm()

    return render(request, 'listings/publish.html', {'form': form})


# 与 publish_view 同样的双门控：@login_required 外层（未登录 302 带 next），
# 内层显式放行 GET/HEAD/POST；重提写入同样要求登录 + is_verified。
@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def resubmit_view(request, pk):
    """修改并重新提交被驳回的商品：作用于本人 rejected 商品，状态经模型层回到 pending。"""

    # 已登录但未认证：统一 200 提示页，且不做商品查询，避免泄露商品存在性。
    if not request.user.is_verified:
        return render(request, 'listings/resubmit.html', {'needs_verification': True})

    # 越权 / 不存在 / 非驳回态统一 404，不泄露商品是否存在；用基础查询集，
    # 不经过 visible()，否则查不到被驳回商品。
    product = get_object_or_404(Product, pk=pk, owner=request.user, status='rejected')
    latest_notice = RejectionNotice.objects.filter(
        product=product, owner=request.user
    ).order_by('-created_at').first()

    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        # 先触发表单校验以建立 form._errors，图片错误才能用 add_error 汇入同一错误区。
        form_valid = form.is_valid()
        images = request.FILES.getlist('images')
        # 重提时图片为可选：不传则保留原图，传了才按 validate_images 校验；
        # 但 0 图商品不传图会退化成无图商品，禁止回到 pending。
        image_errors = validate_images(images) if images else []
        if not images and product.images.count() == 0:
            image_errors.append('该商品暂无图片，请至少上传 1 张商品图片')
        for message in image_errors:
            form.add_error(None, message)

        if form_valid and not image_errors:
            # 五字段更新、可选图片替换与状态流转同成同败；ProductForm 不含 status，
            # 状态请求传值一律忽略，只由模型层 resubmit() 写回 pending。
            with transaction.atomic():
                form.save(commit=False).save()
                if images:
                    product.images.all().delete()
                    for image_file in images:
                        ProductImage.objects.create(product=product, image=image_file)
                product.resubmit()
            return render(request, 'listings/resubmit.html', {
                'submitted': True, 'product': product,
            })
    else:
        form = ProductForm(instance=product)

    return render(request, 'listings/resubmit.html', {
        'form': form,
        'product': product,
        'reason': latest_notice.reason if latest_notice else '',
        'image_count': product.images.count(),
    })


# @login_required 外层：未登录 302 到登录页（带 next）；内层 @require_safe
# 仅放行 GET/HEAD，其余方法 405（Allow: GET, HEAD）且不产生任何写入。
# 卖家本人视图用 Product.objects 基础查询集（不经 visible()），四态全部可见，
# 只读、不改状态、不接受请求传值；排序沿用 Product.Meta.ordering('-created_at')。
@login_required
@require_safe
def my_listings_view(request):
    """我的发布：按 owner=request.user 只读呈现本人全部商品（四态、创建时间倒序）。"""
    my_listings = list(Product.objects.filter(owner=request.user))
    return render(request, 'listings/my_listings.html', {
        'my_listings': my_listings,
        'my_listings_empty': not my_listings,
    })


def _parse_nonnegative_price(raw):
    """把价格字符串解析为非负有限 Decimal；空串 / 非数字 / 负数 / NaN / Inf 返回 None，静默忽略。

    逐条独立校验：一个非法价格不牵连其他有效筛选条件。捕获 InvalidOperation / TypeError /
    ValueError，不向页面抛 ValidationError / InvalidOperation。
    """
    if not raw:
        return None
    try:
        value = Decimal(raw)
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not value.is_finite() or value < 0:
        return None
    return value


# @require_safe 仅放行 GET/HEAD，其余方法 405（Allow: GET, HEAD）且不产生任何写入。
# 买家侧公开只读页：不加 @login_required、不要求 is_verified，匿名 / 已登录均可见。
# 对外可见性唯一门控是 Product.objects.visible()（models.py:12-14），此处直接链式复用，
# 不另写 status 过滤、不写任何状态。关键词 q（strip() 归一化后作整串单一子串、大小写
# 不敏感的标题/描述包含匹配）与 2.7 的 category / condition / min_price / max_price
# 共处于同一 queryset：4 个筛选参数逐条独立归一化与校验（strip() 空串视为未提供、
# 枚举白名单、Decimal 解析、非负、lo > hi 时整对价格条件忽略），有效条件以 AND 链式
# 叠加在 visible() 与 q 链之后，无效者静默忽略、页面恒 200；其余未识别参数一律忽略。
# prefetch_related('images') 一次取回全部首图，消除 N+1；
# 排序沿用 Product.Meta.ordering('-created_at')，全量上架商品均可达，不分页 / 不截断。
@require_safe
def product_list_view(request):
    """商品列表（买家侧，公开只读）：仅上架商品，可按关键词搜索并组合分类/价格/成色筛选。"""
    search_query = request.GET.get('q', '').strip()
    search_active = bool(search_query)

    # 2.7：4 个筛选参数独立归一化；保留 strip() 后的原样值用于控件回显（模板自动转义）。
    filter_category = request.GET.get('category', '').strip()
    filter_condition = request.GET.get('condition', '').strip()
    filter_min_price = request.GET.get('min_price', '').strip()
    filter_max_price = request.GET.get('max_price', '').strip()

    # 枚举白名单：越界值不进入 ORM 查询条件。
    category = (
        filter_category if filter_category in dict(Product.CATEGORY_CHOICES) else ''
    )
    condition = (
        filter_condition if filter_condition in dict(Product.CONDITION_CHOICES) else ''
    )
    min_price = _parse_nonnegative_price(filter_min_price)
    max_price = _parse_nonnegative_price(filter_max_price)
    # 倒置区间：整对价格条件一并忽略（仅 lo > hi 时，不牵连其他有效条件）。
    if min_price is not None and max_price is not None and min_price > max_price:
        min_price = max_price = None

    products_qs = Product.objects.visible()
    if search_active:
        products_qs = products_qs.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )
    # 所有有效条件与 q 链共存于同一 queryset，天然 AND；只提供一端时仅叠加该端。
    if category:
        products_qs = products_qs.filter(category=category)
    if condition:
        products_qs = products_qs.filter(condition=condition)
    if min_price is not None:
        products_qs = products_qs.filter(price__gte=min_price)
    if max_price is not None:
        products_qs = products_qs.filter(price__lte=max_price)

    # 只要有任一有效筛选条件生效，即为筛选态；无效条件静默忽略后退回全量。
    filter_active = any((
        category, condition, min_price is not None, max_price is not None,
    ))
    products = list(products_qs.prefetch_related('images'))

    # 「清空筛选」仅清除 4 个筛选参数并保留 q；无 q 时指向 /listings/。
    clear_filter_url = reverse('product_list')
    if search_query:
        clear_filter_url += '?' + urlencode({'q': search_query})

    return render(request, 'listings/product_list.html', {
        'products': products,
        'products_empty': not products,
        'search_query': search_query,
        'search_active': search_active,
        'result_count': len(products),
        'filter_active': filter_active,
        'filter_category': filter_category,
        'filter_condition': filter_condition,
        'filter_min_price': filter_min_price,
        'filter_max_price': filter_max_price,
        'category_choices': Product.CATEGORY_CHOICES,
        'condition_choices': Product.CONDITION_CHOICES,
        'clear_filter_url': clear_filter_url,
    })


# @require_safe 仅放行 GET/HEAD，其余方法 405（Allow: GET, HEAD）且不产生任何写入。
# 买家侧公开只读详情页：不加 @login_required、不要求 is_verified，匿名 / 已登录 /
# 卖家本人 / admin 均可见同一份商品信息。对外可见性唯一门控是 Product.objects.visible()
# （models.py:12-14），详情查询直接链式复用，不另写 status 过滤、不写任何状态、不按身份分支：
# pending / rejected / offline 与不存在的 pk 一律 404，对任何角色都不放行。
# select_related('owner') 消除卖家信息的额外查询，prefetch_related('images') 一次取回
# 该商品全部图片（查询数不随图片数增长），不分页 / 不缓存 / 不引入索引。
@require_safe
def product_detail_view(request, pk):
    """商品详情（买家侧，公开只读）：仅上架商品，展示全部字段与图片、卖家昵称与认证状态。"""
    product = get_object_or_404(
        Product.objects.visible()
        .select_related('owner')
        .prefetch_related('images'),
        pk=pk,
    )
    return render(request, 'listings/product_detail.html', {'product': product})
