from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.db import transaction
import django.db.models.deletion

from ..models import UserProfile, UserRole

# Custom Forms
class UserForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        user_id = self.instance.id if self.instance else None
        
        # Check if email exists for another user
        if email and User.objects.filter(email=email).exclude(id=user_id).exists():
            raise forms.ValidationError("This email is already in use. Please use a different email.")
        
        return email

class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['phone', 'role']

class UserCreationWithRoleForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    role = forms.ModelChoiceField(queryset=UserRole.objects.all(), required=True)
    phone = forms.CharField(max_length=20, required=False)
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        
        # Check if email exists for any user
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already in use. Please use a different email.")
        
        return email

# Helper function to check if user is admin
def is_admin(user):
    """Check if a user has admin privileges"""
    # Superusers always have admin privileges
    if user.is_superuser:
        return True
    
    # Check for user profile and role
    try:
        # Try to get the user's profile and check if their role is 'Admin'
        profile = UserProfile.objects.get(user=user)
        if profile.role and profile.role.name == 'Admin':
            return True
    except (UserProfile.DoesNotExist, AttributeError):
        # If there's no profile or role, they're not an admin
        pass
    
    return False

@login_required
def user_list(request):
    """Display list of all users"""
    # Only allow admin users to view user list
    if not is_admin(request.user):
        messages.error(request, "You don't have permission to view user list.")
        return redirect('dashboard')
    
    # Get search parameter
    search_query = request.GET.get('search', '')
    
    # Filter users based on search
    users = User.objects.select_related('profile__role').all().order_by('-date_joined')
    
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) | 
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(users, 10)  # Show 10 users per page
    page_number = request.GET.get('page')
    users_page = paginator.get_page(page_number)
    
    context = {
        'users': users_page,
        'search_query': search_query,
    }
    
    # Check if this is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'posapp/users/user_list.html', context)
    
    return render(request, 'posapp/users/user_list.html', context)

@login_required
def user_detail(request, user_id):
    """Display details of a specific user"""
    # Only allow admin users to view user details
    if not is_admin(request.user):
        messages.error(request, "You don't have permission to view user details.")
        return redirect('dashboard')
    
    user = get_object_or_404(User.objects.select_related('profile__role'), id=user_id)
    
    # Get user's order statistics
    from ..models import Order
    from django.db.models import Sum, Count
    from django.utils import timezone
    import datetime
    
    # Calculate today's date range (start and end of day)
    today = timezone.now().date()
    today_start = timezone.make_aware(datetime.datetime.combine(today, datetime.time.min))
    today_end = timezone.make_aware(datetime.datetime.combine(today, datetime.time.max))
    
    # Get total orders
    total_orders = Order.objects.filter(user=user).count()
    total_completed_orders = Order.objects.filter(user=user, order_status='Completed').count()
    total_pending_orders = Order.objects.filter(user=user, order_status='Pending').count()
    
    # Get daily orders (today)
    daily_orders = Order.objects.filter(user=user, created_at__range=(today_start, today_end)).count()
    daily_completed_orders = Order.objects.filter(
        user=user, 
        created_at__range=(today_start, today_end),
        order_status='Completed'
    ).count()
    
    # Get revenue statistics
    total_revenue = Order.objects.filter(
        user=user,
        order_status='Completed'
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    daily_revenue = Order.objects.filter(
        user=user,
        created_at__range=(today_start, today_end),
        order_status='Completed'
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Get recent orders (last 5)
    recent_orders = Order.objects.filter(user=user).order_by('-created_at')[:5]
    
    # Get monthly revenue - last 6 months
    six_months_ago = today - datetime.timedelta(days=180)
    monthly_revenue = []
    
    for i in range(6):
        month_start = today.replace(day=1) - datetime.timedelta(days=30*i)
        if i == 0:
            month_end = today
        else:
            next_month = month_start.replace(day=28) + datetime.timedelta(days=4)
            month_end = next_month.replace(day=1) - datetime.timedelta(days=1)
        
        month_start_aware = timezone.make_aware(datetime.datetime.combine(month_start, datetime.time.min))
        month_end_aware = timezone.make_aware(datetime.datetime.combine(month_end, datetime.time.max))
        
        month_revenue = Order.objects.filter(
            user=user,
            created_at__range=(month_start_aware, month_end_aware),
            order_status='Completed'
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        monthly_revenue.append({
            'month': month_start.strftime('%b %Y'),
            'revenue': month_revenue
        })
    
    # Reverse the list to show oldest to newest
    monthly_revenue.reverse()
    
    # Calculate percentages for the progress bars
    if total_orders > 0:
        pending_percentage = (total_pending_orders / total_orders) * 100
        completed_percentage = (total_completed_orders / total_orders) * 100
    else:
        pending_percentage = 0
        completed_percentage = 0
        
    if daily_orders > 0:
        daily_completed_percentage = (daily_completed_orders / daily_orders) * 100
    else:
        daily_completed_percentage = 0
    
    context = {
        'user_obj': user,
        'total_orders': total_orders,
        'total_completed_orders': total_completed_orders,
        'total_pending_orders': total_pending_orders,
        'daily_orders': daily_orders,
        'daily_completed_orders': daily_completed_orders,
        'total_revenue': total_revenue,
        'daily_revenue': daily_revenue,
        'recent_orders': recent_orders,
        'monthly_revenue': monthly_revenue,
        'pending_percentage': pending_percentage,
        'completed_percentage': completed_percentage,
        'daily_completed_percentage': daily_completed_percentage,
    }
    
    return render(request, 'posapp/users/user_detail.html', context)

@login_required
def user_create(request):
    """Create a new user"""
    # Only allow admin users to create users
    if not is_admin(request.user):
        messages.error(request, "You don't have permission to create users.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserCreationWithRoleForm(request.POST)
        if form.is_valid():
            # Use transaction to ensure all operations succeed or fail together
            try:
                with transaction.atomic():
                    user = form.save()
                    # Create user profile
                    profile, created = UserProfile.objects.get_or_create(
                        user=user,
                        defaults={
                            'phone': form.cleaned_data['phone'],
                            'role': form.cleaned_data['role'],
                            'is_active': True
                        }
                    )
                    
                    # If profile exists but wasn't created now, update it
                    if not created:
                        profile.phone = form.cleaned_data['phone']
                        profile.role = form.cleaned_data['role']
                        profile.save()
                        
                messages.success(request, f'User {user.username} created successfully.')
                return redirect('user_list')
            except Exception as e:
                # If something went wrong, display the error
                messages.error(request, f"Error creating user: {str(e)}")
        else:
            # Display form validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = UserCreationWithRoleForm()
    
    context = {
        'form': form,
        'title': 'Create New User',
    }
    
    return render(request, 'posapp/users/user_form.html', context)

@login_required
def user_edit(request, user_id):
    """Edit an existing user"""
    # Only allow admin users to edit users
    if not is_admin(request.user):
        messages.error(request, "You don't have permission to edit users.")
        return redirect('dashboard')
    
    user = get_object_or_404(User, id=user_id)
    
    # Try to get the profile, but don't fail if it doesn't exist
    try:
        profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        profile = None
    
    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=user)
        profile_form = ProfileForm(request.POST, instance=profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            try:
                with transaction.atomic():
                    # Save user data
                    user_form.save()
                    
                    # Save or create profile
                    if profile:
                        profile_form.save()
                    else:
                        # Create profile if it doesn't exist
                        UserProfile.objects.create(
                            user=user,
                            phone=profile_form.cleaned_data['phone'],
                            role=profile_form.cleaned_data['role']
                        )
                
                messages.success(request, f'User {user.username} updated successfully.')
                return redirect('user_detail', user_id=user.id)
            except Exception as e:
                messages.error(request, f"Error updating user: {str(e)}")
        else:
            # Display form validation errors
            for form in [user_form, profile_form]:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
    else:
        user_form = UserForm(instance=user)
        profile_form = ProfileForm(instance=profile)
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'title': f'Edit User {user.username}',
        'user_obj': user,
    }
    
    return render(request, 'posapp/users/user_edit.html', context)

@login_required
def user_delete(request, user_id):
    """Delete a user"""
    # Only allow admin users to delete users
    if not is_admin(request.user):
        messages.error(request, "You don't have permission to delete users.")
        return redirect('dashboard')
    
    user = get_object_or_404(User, id=user_id)
    
    # Prevent self-deletion
    if user.id == request.user.id:
        messages.error(request, "You cannot delete your own account.")
        return redirect('user_list')
    
    if request.method == 'POST':
        try:
            username = user.username
            user.delete()
            messages.success(request, f'User {username} deleted successfully.')
            return redirect('user_list')
        except django.db.models.deletion.ProtectedError as e:
            # Deactivate the user instead of deleting
            deactivate_user(user)
            messages.warning(request, f"User {user.username} could not be deleted because they have associated orders. The user has been deactivated instead.")
            return redirect('user_list')
    
    context = {
        'user_obj': user,
    }
    
    return render(request, 'posapp/users/user_confirm_delete.html', context)

def deactivate_user(user):
    """Deactivate a user instead of deleting them"""
    # Set is_active to False on the User
    user.is_active = False
    user.save()
    
    # Also deactivate their profile if it exists
    try:
        if hasattr(user, 'profile'):
            user.profile.is_active = False
            user.profile.save()
    except Exception:
        pass  # If there's no profile, just continue
    
    return True 