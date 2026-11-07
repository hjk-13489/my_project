from django import forms
from .models import User


class LoginForm(forms.Form):
    student_id = forms.CharField(
        label='学号',
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入学号'}),
        error_messages={'required': '请输入学号'},
    )
    password = forms.CharField(
        label='密码',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '请输入密码'}),
        error_messages={'required': '请输入密码'},
    )


class RegisterForm(forms.ModelForm):
    password = forms.CharField(
        label='密码',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '请输入密码（至少6位）'}),
    )
    password_confirm = forms.CharField(
        label='确认密码',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '请再次输入密码'}),
    )

    class Meta:
        model = User
        fields = ['student_id', 'username']
        labels = {
            'student_id': '学号',
            'username': '昵称',
        }
        widgets = {
            'student_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入学号'}),
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '请输入昵称'}),
        }
        error_messages = {
            'student_id': {
                'required': '请输入学号',
                'unique': '该学号已被注册',
            },
            'username': {
                'required': '请输入昵称',
                'unique': '该昵称已被使用',
            },
        }

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if len(password) < 6:
            raise forms.ValidationError('密码长度不能少于 6 位')
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', '两次输入的密码不一致')
        return cleaned_data