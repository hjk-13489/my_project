from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('verify/', views.verify_view, name='verify'),
    path('profile/', views.profile_view, name='profile'),
]
