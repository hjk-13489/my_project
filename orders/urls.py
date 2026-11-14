from django.urls import path

from . import views

urlpatterns = [
    path('create/<int:product_pk>/', views.order_create, name='order_create'),
    path('<int:pk>/', views.order_detail, name='order_detail'),
    path('<int:pk>/pay/', views.order_pay, name='order_pay'),
]
