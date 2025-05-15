from django.urls import path
from django.shortcuts import render
from .views import (
    LoginView, LogoutView, change_password,
    dashboard, pos, end_day, sales_summary
)
from .views.product_views import (
    product_list, product_detail, product_create, 
    product_edit, product_delete, product_archive,
    check_product_stock, get_products_stock
)
from .views.category_views import (
    category_list, category_detail, category_create,
    category_edit, category_delete
)
from .views.order_views import (
    order_list, order_detail, order_create, 
    order_edit, order_delete, order_receipt,
    add_order_item, delete_order_item, create_order_api,
    complete_order, mark_order_paid, increase_order_item,
    kitchen_receipt, get_active_tables
)
from .views.discount_views import (
    discount_list, discount_detail, discount_create,
    discount_edit, discount_delete, validate_discount_code
)
from .views.reports_views import (
    reports_dashboard, sales_report,
    export_orders_excel, export_order_items_excel,
    sales_receipt, sales_summary_history, sales_summary_detail
)
from .views.user_views import (
    user_list, user_detail, user_create,
    user_edit, user_delete
)
from .views.settings_views import (
    settings_dashboard,
    business_settings,
    receipt_settings,
    theme_settings,
)
from .views.adjustment_views import (
    adjustment_dashboard, adjustment_report,
    BillAdjustmentListView, BillAdjustmentDetailView, 
    BillAdjustmentCreateView, BillAdjustmentUpdateView, BillAdjustmentDeleteView,
    BillAdjustmentImageDeleteView,
    AdvanceAdjustmentListView, AdvanceAdjustmentDetailView,
    AdvanceAdjustmentCreateView, AdvanceAdjustmentUpdateView, AdvanceAdjustmentDeleteView,
    adjustment_receipt
)
from .views.image_views import (
    serve_product_image,
    serve_business_logo,
    serve_bill_adjustment_image
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
    path('end-day/', end_day, name='end_day'),
    path('sales-summary/', sales_summary, name='sales_summary'),
    path('sales-summary/<int:end_day_id>/', sales_summary, name='sales_summary'),
    
    # Profile route
    path('profile/', profile_view, name='profile'),
    
    # Product management
    path('products/', product_list, name='product_list'),
    path('products/create/', product_create, name='product_create'),
    path('products/<int:product_id>/', product_detail, name='product_detail'),
    path('products/<int:product_id>/edit/', product_edit, name='product_edit'),
    path('products/<int:product_id>/delete/', product_delete, name='product_delete'),
    path('products/<int:product_id>/archive/', product_archive, name='product_archive'),
    
    # Category management
    path('categories/', category_list, name='category_list'),
    path('categories/create/', category_create, name='category_create'),
    path('categories/<int:category_id>/', category_detail, name='category_detail'),
    path('categories/<int:category_id>/edit/', category_edit, name='category_edit'),
    path('categories/<int:category_id>/delete/', category_delete, name='category_delete'),
    
    # Order management - orders are created from POS section only
    path('orders/', order_list, name='order_list'),
    path('orders/<int:order_id>/', order_detail, name='order_detail'),
    path('orders/<int:order_id>/edit/', order_edit, name='order_edit'),
    path('orders/<int:order_id>/cancel/', order_delete, name='order_cancel'),
    path('orders/<int:order_id>/complete/', complete_order, name='order_complete'),
    path('orders/<int:order_id>/mark-paid/', mark_order_paid, name='order_mark_paid'),
    path('orders/<int:order_id>/receipt/', order_receipt, name='order_receipt'),
    path('orders/<int:order_id>/kitchen/', kitchen_receipt, name='kitchen_receipt'),
    path('orders/<int:order_id>/add-item/', add_order_item, name='add_order_item'),
    path('orders/<int:order_id>/delete-item/<int:item_id>/', delete_order_item, name='delete_order_item'),
    path('orders/<int:order_id>/increase-item/<int:item_id>/', increase_order_item, name='increase_order_item'),
    
    # API endpoints
    path('api/orders/', create_order_api, name='create_order_api'),
    path('api/discounts/validate/', validate_discount_code, name='validate_discount_code'),
    path('api/products/<int:product_id>/check-stock/', check_product_stock, name='check_product_stock'),
    path('api/products/stock/', get_products_stock, name='get_products_stock'),
    path('api/tables/active/', get_active_tables, name='get_active_tables'),
    
    # Discount management
    path('discounts/', discount_list, name='discount_list'),
    path('discounts/create/', discount_create, name='discount_create'),
    path('discounts/<int:discount_id>/', discount_detail, name='discount_detail'),
    path('discounts/<int:discount_id>/edit/', discount_edit, name='discount_edit'),
    path('discounts/<int:discount_id>/delete/', discount_delete, name='discount_delete'),
    
    # Reports
    path('reports/', reports_dashboard, name='reports_dashboard'),
    path('reports/sales/', sales_report, name='sales_report'),
    path('reports/sales/receipt/', sales_receipt, name='sales_receipt'),
    path('reports/sales/history/', sales_summary_history, name='sales_summary_history'),
    path('reports/sales/history/<int:pk>/', sales_summary_detail, name='sales_summary_detail'),
    path('reports/export/orders/', export_orders_excel, name='export_orders_excel'),
    path('reports/export/order_items/', export_order_items_excel, name='export_order_items_excel'),
    path('reports/adjustments/', adjustment_report, name='adjustment_report'),
    path('reports/adjustments/receipt/', adjustment_receipt, name='adjustment_receipt'),
    
    # User management
    path('users/', user_list, name='user_list'),
    path('users/create/', user_create, name='user_create'),
    path('users/<int:user_id>/', user_detail, name='user_detail'),
    path('users/<int:user_id>/edit/', user_edit, name='user_edit'),
    path('users/<int:user_id>/delete/', user_delete, name='user_delete'),
    
    # Settings
    path('settings/', settings_dashboard, name='settings_dashboard'),
    path('settings/business/', business_settings, name='business_settings'),
    path('settings/receipt/', receipt_settings, name='receipt_settings'),
    path('settings/theme/', theme_settings, name='theme_settings'),
    
    # Images served from database
    path('product_image/<int:product_id>/', serve_product_image, name='serve_product_image'),
    path('business_logo/<int:logo_id>/', serve_business_logo, name='serve_business_logo'),
    path('bill_adjustment_image/<int:image_id>/', serve_bill_adjustment_image, name='serve_bill_adjustment_image'),
    
    # Adjustments
    path('adjustments/', adjustment_dashboard, name='adjustment_dashboard'),
    
    # Bill Adjustments
    path('adjustments/bills/', BillAdjustmentListView.as_view(), name='bill_adjustment_list'),
    path('adjustments/bills/create/', BillAdjustmentCreateView.as_view(), name='bill_adjustment_create'),
    path('adjustments/bills/<int:pk>/', BillAdjustmentDetailView.as_view(), name='bill_adjustment_detail'),
    path('adjustments/bills/<int:pk>/edit/', BillAdjustmentUpdateView.as_view(), name='bill_adjustment_edit'),
    path('adjustments/bills/<int:pk>/delete/', BillAdjustmentDeleteView.as_view(), name='bill_adjustment_delete'),
    path('adjustments/bills/images/<int:pk>/delete/', BillAdjustmentImageDeleteView.as_view(), name='bill_adjustment_image_delete'),
    
    # Advance Adjustments
    path('adjustments/advances/', AdvanceAdjustmentListView.as_view(), name='advance_adjustment_list'),
    path('adjustments/advances/create/', AdvanceAdjustmentCreateView.as_view(), name='advance_adjustment_create'),
    path('adjustments/advances/<int:pk>/', AdvanceAdjustmentDetailView.as_view(), name='advance_adjustment_detail'),
    path('adjustments/advances/<int:pk>/edit/', AdvanceAdjustmentUpdateView.as_view(), name='advance_adjustment_edit'),
    path('adjustments/advances/<int:pk>/delete/', AdvanceAdjustmentDeleteView.as_view(), name='advance_adjustment_delete'),
] 