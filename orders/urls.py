from django.urls import path

from . import views

urlpatterns = [
    path('create/<int:product_pk>/', views.order_create, name='order_create'),
    # 静态列表路由置于 <int:pk>/ 之前，避免被动态路由吞掉。
    path('mine/', views.my_orders_view, name='my_orders'),
    path('sold/', views.sold_orders_view, name='sold_orders'),
    path('<int:pk>/', views.order_detail, name='order_detail'),
    path('<int:pk>/pay/', views.order_pay, name='order_pay'),
    path('<int:pk>/confirm-receipt/', views.order_confirm_receipt,
         name='order_confirm_receipt'),
]
