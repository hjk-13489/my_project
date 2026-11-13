"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import render
from django.urls import include, path


def home(request):
    return render(request, "index.html")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("", include("accounts.urls")),
    # 追加项不排在既有 path("", ...) 之前，避免抢占既有路由。
    path("listings/", include("listings.urls")),
    path("orders/", include("orders.urls")),
]

# 开发期媒体服务（闭合 deferred-work.md 中登记的待办）。
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
