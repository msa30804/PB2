from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.contrib.auth.models import User
from django.contrib import messages
from ..models import Category, Product, Order, UserProfile, Setting, BusinessSettings

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
def dashboard(request):
    # Check if user has admin access
    if not is_admin(request.user):
        messages.error(request, "You don't have permission to access the dashboard.")
        return redirect('pos')
        
    # Fetch summary data
    total_products = Product.objects.count()
    total_categories = Category.objects.count()
    total_users = User.objects.count()
    total_orders = Order.objects.count()
    
    # Count active orders (exclude cancelled orders)
    active_orders = Order.objects.exclude(order_status='Cancelled').count()
    
    # Revenue calculation (exclude cancelled orders)
    total_revenue = Order.objects.exclude(order_status='Cancelled').aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Recent products (latest 5)
    recent_products = Product.objects.all().order_by('-created_at')[:5]
    
    # Recent orders (latest 5)
    recent_orders = Order.objects.all().order_by('-created_at')[:5]
    
    # Top selling products - since sold_count doesn't exist, 
    # we'll just use the most expensive products instead
    top_products = Product.objects.all().order_by('-price')[:5]
    
    # All categories
    categories = Category.objects.all()
    
    # All users with their roles
    users = User.objects.select_related('profile__role').all()
    
    # Get business information
    business_settings = {}
    for setting in Setting.objects.filter(setting_key__in=['business_name', 'business_address', 'business_phone', 'tax_rate']):
        business_settings[setting.setting_key] = setting.setting_value
    
    context = {
        'total_products': total_products,
        'total_categories': total_categories,
        'total_users': total_users,
        'total_orders': total_orders,
        'active_orders': active_orders,
        'total_revenue': total_revenue,
        'recent_products': recent_products,
        'recent_orders': recent_orders,
        'top_products': top_products,
        'categories': categories,
        'users': users,
        'business_settings': business_settings,
    }
    
    return render(request, 'posapp/dashboard.html', context)

@login_required
def pos(request):
    # Fetch all products and categories for the POS interface
    products = Product.objects.all()
    categories = Category.objects.all()
    
    # Set tax rates
    card_tax_rate = 5
    standard_tax_rate = 15
    
    context = {
        'products': products,
        'categories': categories,
        'card_tax_rate': card_tax_rate,
        'standard_tax_rate': standard_tax_rate,
    }
    
    return render(request, 'posapp/pos.html', context) 