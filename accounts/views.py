from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import render, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from .forms import LoginForm, RegisterForm, VerificationForm
from .models import VerificationRequest


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
