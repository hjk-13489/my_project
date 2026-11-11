from django.urls import path
from . import views

urlpatterns = [
    path('publish/', views.publish_view, name='publish'),
    path('<int:pk>/resubmit/', views.resubmit_view, name='resubmit'),
    path('mine/', views.my_listings_view, name='my_listings'),
    path('', views.product_list_view, name='product_list'),
]
