from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.models import User
from ..forms import CustomAuthenticationForm
from ..models import AuditLog, UserProfile, UserRole

class LoginView(View):
    template_name = 'posapp/auth/login.html'
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        form = CustomAuthenticationForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = CustomAuthenticationForm(data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            
            if user is not None:
                login(request, user)
                
                # Ensure user profile exists
                if not hasattr(user, 'profile'):
                    # Get default role (Cashier or create it if it doesn't exist)
                    default_role, _ = UserRole.objects.get_or_create(
                        name='Cashier',
                        defaults={'description': 'Cashier with limited access'}
                    )
                    
                    # If user is superuser or staff, make them Admin
                    if user.is_superuser or user.is_staff:
                        admin_role, _ = UserRole.objects.get_or_create(
                            name='Admin',
                            defaults={'description': 'Administrator with full access'}
                        )
                        UserProfile.objects.create(user=user, role=admin_role)
                    else:
                        UserProfile.objects.create(user=user, role=default_role)
                
                next_url = request.GET.get('next', 'dashboard')
                return redirect(next_url)
        
        # If form is invalid, show error messages
        messages.error(request, 'Invalid username or password')
        return render(request, self.template_name, {'form': form})

class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect('login')

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'posapp/auth/change_password.html', {'form': form})