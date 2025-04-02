from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.contrib.auth.models import User
from ..models import Category, Product, Order, UserProfile, Setting

@login_required
def dashboard(request):
    # Fetch summary data
    total_products = Product.objects.count()
    total_categories = Category.objects.count()
    total_users = User.objects.count()
    total_orders = Order.objects.count()
    
    # Revenue calculation (if there are orders)
    total_revenue = Order.objects.aggregate(total=Sum('total_amount'))['total'] or 0
    
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
    
    # Set tax rate to 15%
    tax_rate_value = 15
    
    context = {
        'products': products,
        'categories': categories,
        'tax_rate': tax_rate_value,
    }
    
    return render(request, 'posapp/pos.html', context) 