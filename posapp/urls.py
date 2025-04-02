from django.urls import path
from django.shortcuts import render
from .views import (
    LoginView, LogoutView, change_password,
    dashboard, pos
)

# Simple profile view function
def profile_view(request):
    return render(request, 'posapp/profile.html')

urlpatterns = [
    # Authentication URLs
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('change-password/', change_password, name='change_password'),
    
    # Dashboard
    path('', dashboard, name='dashboard'),
    path('pos/', pos, name='pos'),
    
    # Profile route
    path('profile/', profile_view, name='profile'),
    
    # These will be implemented in separate view files
    # User management
    # path('users/', user_list, name='user_list'),
    # path('users/create/', user_create, name='user_create'),
    # path('users/<int:user_id>/', user_detail, name='user_detail'),
    # path('users/<int:user_id>/edit/', user_edit, name='user_edit'),
    # path('users/<int:user_id>/delete/', user_delete, name='user_delete'),
    
    # Category management
    # path('categories/', category_list, name='category_list'),
    # path('categories/create/', category_create, name='category_create'),
    # path('categories/<int:category_id>/', category_detail, name='category_detail'),
    # path('categories/<int:category_id>/edit/', category_edit, name='category_edit'),
    # path('categories/<int:category_id>/delete/', category_delete, name='category_delete'),
    
    # Product management
    # path('products/', product_list, name='product_list'),
    # path('products/create/', product_create, name='product_create'),
    # path('products/<int:product_id>/', product_detail, name='product_detail'),
    # path('products/<int:product_id>/edit/', product_edit, name='product_edit'),
    # path('products/<int:product_id>/delete/', product_delete, name='product_delete'),
    
    # Order management
    # path('orders/', order_list, name='order_list'),
    # path('orders/create/', order_create, name='order_create'),
    # path('orders/<int:order_id>/', order_detail, name='order_detail'),
    # path('orders/<int:order_id>/edit/', order_edit, name='order_edit'),
    # path('orders/<int:order_id>/delete/', order_delete, name='order_delete'),
    # path('orders/<int:order_id>/receipt/', order_receipt, name='order_receipt'),
    
    # Discount management
    # path('discounts/', discount_list, name='discount_list'),
    # path('discounts/create/', discount_create, name='discount_create'),
    # path('discounts/<int:discount_id>/', discount_detail, name='discount_detail'),
    # path('discounts/<int:discount_id>/edit/', discount_edit, name='discount_edit'),
    # path('discounts/<int:discount_id>/delete/', discount_delete, name='discount_delete'),
    
    # Reports
    # path('reports/sales/', sales_report, name='sales_report'),
    # path('reports/inventory/', inventory_report, name='inventory_report'),
    # path('reports/users/', user_report, name='user_report'),
    
    # Settings
    # path('settings/', settings_view, name='settings'),
    # path('settings/receipt/', receipt_settings, name='receipt_settings'),
    # path('settings/tax/', tax_settings, name='tax_settings'),
    # path('settings/business/', business_settings, name='business_settings'),
] 