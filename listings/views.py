from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .forms import ProductForm, validate_images
from .models import ProductImage


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
