from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import render, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST, require_safe
from .forms import LoginForm, RegisterForm, VerificationForm
from .models import VerificationRequest
from listings.models import Product, RejectionNotice


def register(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            try:
                user.save()
            except IntegrityError as e:
                if 'student_id' in str(e):
                    form.add_error('student_id', '该学号已被注册')
                else:
                    form.add_error('username', '该昵称已被使用')
                return render(request, 'accounts/register.html', {'form': form})
            login(request, user)
            return redirect('home')
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            student_id = form.cleaned_data['student_id']
            password = form.cleaned_data['password']
            user = authenticate(request, username=student_id, password=password)
            if user is not None:
                login(request, user)
                next_url = request.GET.get('next') or 'home'
                if not url_has_allowed_host_and_scheme(next_url, allowed_hosts=None):
                    next_url = 'home'
                return redirect(next_url)
            else:
                form.add_error(None, '学号或密码错误')
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


@require_POST
def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def verify_view(request):
    """学号身份认证提交页（仅已登录且未认证用户可访问）。"""
    if request.user.is_verified:
        return redirect('home')

    pending_request = VerificationRequest.objects.filter(
        user=request.user, status='pending'
    ).first()
    initial = {'student_id': request.user.student_id}

    if request.method == 'POST':
        if pending_request is not None:
            return render(request, 'accounts/verify.html', {
                'pending_request': pending_request,
                'duplicate_error': '你已有待审核的认证申请',
            })

        form = VerificationForm(request.POST, initial=initial)
        if form.is_valid():
            student_id = form.cleaned_data['student_id']
            name = form.cleaned_data['name']
            rejected_request = VerificationRequest.objects.filter(
                user=request.user, status='rejected'
            ).order_by('-created_at').first()
            try:
                if rejected_request is not None:
                    # 被驳回后重新提交：更新原记录，不创建新记录
                    rejected_request.student_id = student_id
                    rejected_request.name = name
                    rejected_request.status = 'pending'
                    rejected_request.save()
                else:
                    VerificationRequest.objects.create(
                        user=request.user,
                        student_id=student_id,
                        name=name,
                        status='pending',
                    )
            except IntegrityError:
                # 数据库唯一约束兜底（并发重复提交）
                return render(request, 'accounts/verify.html', {
                    'pending_request': True,
                    'duplicate_error': '你已有待审核的认证申请',
                })
            return render(request, 'accounts/verify.html', {'submitted': True})
    else:
        form = VerificationForm(initial=initial)

    return render(request, 'accounts/verify.html', {
        'form': form,
        'pending_request': pending_request,
    })


# require_safe 放行 GET/HEAD：规格要求仅非 GET/HEAD 才 405，故不用仅放行 GET 的 require_GET。
@login_required
@require_safe
def profile_view(request):
    """个人中心：只读展示本人账号信息、认证申请历史与本人驳回通知，其余板块空状态占位。"""
    profile_user = request.user
    # 「我的消息」按 owner=request.user 服务端过滤，仅本人可见；通知实体不随
    # 商品状态变化而删除，故重提后历史驳回理由仍可在此看到。
    my_messages = list(
        RejectionNotice.objects.filter(owner=profile_user)
        .select_related('product')
        .order_by('-created_at')
    )
    # 「我的发布」按 owner=profile_user 从 Product.objects 基础查询集取回本人全部商品，
    # 不经 visible()，四态（pending/approved/rejected/offline）对卖家本人均可见；
    # 只读展示，排序沿用 Product.Meta.ordering('-created_at')。
    my_listings = list(Product.objects.filter(owner=profile_user))
    return render(request, 'accounts/profile.html', {
        'profile_user': profile_user,
        'verification_requests': profile_user.verification_requests.all(),
        # 方案 A「壳 + 空状态」：订单 / 评价两板块暂无业务数据，统一空状态；Epic 3/4
        # 接入真实数据时，以 filter(buyer=profile_user) / filter(owner=profile_user) 替换。
        'my_listings': my_listings,
        'my_listings_empty': not my_listings,
        'my_orders_empty': True,
        'my_messages': my_messages,
        'my_messages_empty': not my_messages,
        'my_reviews_empty': True,
    })
