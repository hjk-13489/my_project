from django.contrib.auth import authenticate, login, logout
from django.db import IntegrityError
from django.shortcuts import render, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from .forms import LoginForm, RegisterForm


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
