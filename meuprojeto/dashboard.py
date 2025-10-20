from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.utils import timezone

@login_required(login_url='login')
def dashboard_view(request):
    context = {
        'username': request.user.username,
        'last_login': request.user.last_login,
        'current_time': timezone.now(),
        'total_users': User.objects.count(),
        'is_admin': request.user.is_superuser,
    }
    return render(request, 'dashboard.html', context)
