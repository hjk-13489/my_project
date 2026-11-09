from django.urls import path
from . import views

urlpatterns = [
    path('publish/', views.publish_view, name='publish'),
    path('<int:pk>/resubmit/', views.resubmit_view, name='resubmit'),
]
