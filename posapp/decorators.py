from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps
from django.urls import reverse

from .views.dashboard_views import is_admin, is_branch_manager

def admin_required(view_func):
    """
    Decorator for views that checks if the user is an admin.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not is_admin(request.user):
            messages.error(request, "You don't have permission to access this page. Admin access required.")
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def management_required(view_func):
    """
    Decorator for views that checks if the user is an admin or branch manager.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not (is_admin(request.user) or is_branch_manager(request.user)):
            messages.error(request, "You don't have permission to access this page. Management access required.")
            return redirect('pos')
        return view_func(request, *args, **kwargs)
    return _wrapped_view 