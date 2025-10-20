"""
URL configuration for meuprojeto project.

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
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from .demo import demo_view
from .dashboard import dashboard_view
from django.shortcuts import redirect
from django.http import FileResponse, HttpResponseNotFound
from django.conf import settings
from django.templatetags.static import static

def redirect_to_login(request):
    return redirect('login')

def redirect_to_dashboard(request):
    return redirect('dashboard')

urlpatterns = [
    path('', redirect_to_login, name='home'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('admin/', admin.site.urls),
    path('accounts/login/', auth_views.LoginView.as_view(redirect_authenticated_user=True), name='login'),
    path('accounts/profile/', redirect_to_dashboard, name='profile'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('demo/', demo_view, name='demo'),
    path('stock/', include('meuprojeto.empresa.urls_stock')),
    path('rh/', include('meuprojeto.empresa.urls_rh')),
    # Fallback para /favicon.ico
    path('favicon.ico', lambda request: redirect(static('admin/img/icon-yes.svg'))),
]
