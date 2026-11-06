from django.contrib.auth import login
from django.db import IntegrityError
from django.shortcuts import render, redirect
from .forms import RegisterForm


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
            except IntegrityError:
                form.add_error('student_id', '该学号已被注册')
                return render(request, 'accounts/register.html', {'form': form})
            login(request, user)
            return redirect('home')
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})