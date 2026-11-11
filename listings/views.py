from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, render
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


# @require_safe 仅放行 GET/HEAD，其余方法 405（Allow: GET, HEAD）且不产生任何写入。
# 买家侧公开只读页：不加 @login_required、不要求 is_verified，匿名 / 已登录均可见。
# 对外可见性唯一门控是 Product.objects.visible()（models.py:12-14），此处直接链式复用，
# 不另写 status 过滤、不写任何状态、不接受请求传值做筛选或排序；
# prefetch_related('images') 一次取回全部首图，消除 N+1；
# 排序沿用 Product.Meta.ordering('-created_at')，全量上架商品均可达，不分页 / 不截断。
@require_safe
def product_list_view(request):
    """商品列表（买家侧，公开只读）：仅上架商品，含缩略图 / 标题 / 价格 / 中文成色。"""
    products = list(Product.objects.visible().prefetch_related('images'))
    return render(request, 'listings/product_list.html', {
        'products': products,
        'products_empty': not products,
    })
