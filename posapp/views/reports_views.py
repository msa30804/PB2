from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F, DecimalField, Value
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, Coalesce
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.contrib import messages
from datetime import datetime, timedelta
from decimal import Decimal
import csv
import json
from django.db.models import Q
from django.core.cache import cache
import logging
from django.core.paginator import Paginator

# Try to import xlwt for Excel export, but make it optional
EXCEL_EXPORT_AVAILABLE = False
try:
    import xlwt
    EXCEL_EXPORT_AVAILABLE = True
except ImportError:
    print("xlwt not installed. Excel export will be disabled.")
except Exception as e:
    print(f"xlwt error: {e}")

from ..models import Order, OrderItem, Product, Category, BusinessSettings, BillAdjustment, AdvanceAdjustment, BusinessLogo, Setting, EndDay, SalesSummary
from ..decorators import management_required

# Set up logger
logger = logging.getLogger('posapp')

@login_required
@management_required
def reports_dashboard(request):
    """Main reports dashboard with overview of available reports"""
    
    # Check if user is admin or branch manager
    is_admin = request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role.name == 'Admin')
    
    # Get the last end day timestamp
    last_end_day = EndDay.get_last_end_day()
    last_end_day_time = last_end_day.end_date if last_end_day else None
    
    # Get some overview stats
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Base query for filtering orders
    if is_admin or not last_end_day_time:
        # Admin sees all orders, or if no end day exists, show all
        base_query = Order.objects.all()
    else:
        # Branch manager sees only orders since last end day
        base_query = Order.objects.filter(created_at__gte=last_end_day_time)
    
    # Orders count (exclude cancelled orders)
    orders_today = base_query.filter(created_at__date=today).exclude(order_status='Cancelled').count()
    orders_week = base_query.filter(created_at__date__gte=week_ago).exclude(order_status='Cancelled').count()
    orders_month = base_query.filter(created_at__date__gte=month_ago).exclude(order_status='Cancelled').count()
    orders_total = base_query.exclude(order_status='Cancelled').count()
    
    # Revenue (exclude cancelled orders)
    revenue_today = base_query.filter(created_at__date=today).exclude(order_status='Cancelled').aggregate(total=Sum('total_amount'))['total'] or 0
    revenue_week = base_query.filter(created_at__date__gte=week_ago).exclude(order_status='Cancelled').aggregate(total=Sum('total_amount'))['total'] or 0
    revenue_month = base_query.filter(created_at__date__gte=month_ago).exclude(order_status='Cancelled').aggregate(total=Sum('total_amount'))['total'] or 0
    revenue_total = base_query.exclude(order_status='Cancelled').aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Get categories for the product export filter
    categories = Category.objects.all()
    
    context = {
        'orders_today': orders_today,
        'orders_week': orders_week,
        'orders_month': orders_month,
        'orders_total': orders_total,
        'revenue_today': revenue_today,
        'revenue_week': revenue_week,
        'revenue_month': revenue_month,
        'revenue_total': revenue_total,
        'categories': categories,
        'excel_export_available': EXCEL_EXPORT_AVAILABLE,
        'is_admin': is_admin,
        'last_end_day': last_end_day,
    }
    
    return render(request, 'posapp/reports/dashboard.html', context)


@login_required
@management_required
def sales_report(request):
    """Sales report with charts and data"""
    
    # Check if user is admin or branch manager
    is_admin = request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role.name == 'Admin')
    
    # Get the last end day timestamp
    last_end_day = EndDay.get_last_end_day()
    last_end_day_time = last_end_day.end_date if last_end_day else None
    
    # Handle date range selection
    report_type = request.GET.get('report_type', 'daily')
    date_range = request.GET.get('date_range', '7days')
    custom_start = request.GET.get('start', '')
    custom_end = request.GET.get('end', '')
    
    # Calculate date range based on selection
    today = timezone.now().date()
    if date_range == '7days':
        start_date = today - timedelta(days=6)
        end_date = today
    elif date_range == '30days':
        start_date = today - timedelta(days=29)
        end_date = today
    elif date_range == 'this_month':
        start_date = today.replace(day=1)
        end_date = today
    elif date_range == 'last_month':
        last_month = today.month - 1 if today.month > 1 else 12
        last_month_year = today.year if today.month > 1 else today.year - 1
        start_date = datetime(last_month_year, last_month, 1).date()
        if last_month == 12:
            end_date = datetime(last_month_year, last_month, 31).date()
        else:
            end_date = datetime(last_month_year, last_month + 1, 1).date() - timedelta(days=1)
    elif date_range == 'this_year':
        start_date = today.replace(month=1, day=1)
        end_date = today
    elif date_range == 'custom' and custom_start and custom_end:
        start_date = datetime.strptime(custom_start, '%Y-%m-%d').date()
        end_date = datetime.strptime(custom_end, '%Y-%m-%d').date()
    else:
        # Default to last 7 days
        start_date = today - timedelta(days=6)
        end_date = today
    
    # Get sales data grouped by day/week/month
    if report_type == 'daily':
        truncate_date = TruncDay('created_at')
    elif report_type == 'weekly':
        truncate_date = TruncWeek('created_at')
    else:  # monthly
        truncate_date = TruncMonth('created_at')
    
    # For branch managers, further limit by last end day if needed
    base_filter = Q(created_at__date__gte=start_date, created_at__date__lte=end_date)
    
    if not is_admin and last_end_day_time:
        # Add condition for branch managers to only see data since last end day
        base_filter &= Q(created_at__gte=last_end_day_time)
    
    # Get sales data excluding cancelled orders
    sales_data = Order.objects.filter(
        base_filter
    ).exclude(
        order_status='Cancelled'
    ).annotate(
        date=truncate_date
    ).values('date').annotate(
        total_sales=Sum('total_amount'),
        order_count=Count('id')
    ).order_by('date')
    
    # Top selling products (exclude orders that were cancelled)
    top_products = OrderItem.objects.filter(
        order__in=Order.objects.filter(base_filter),
        order__order_status='Completed'  # Only include completed orders
    ).values('product__name', 'product__category__name').annotate(
        total_quantity=Sum('quantity'),
        total_sales=Sum('total_price')
    ).order_by('-total_quantity')[:10]
    
    # Sales by category (exclude orders that were cancelled)
    category_sales = OrderItem.objects.filter(
        order__in=Order.objects.filter(base_filter)
    ).exclude(
        order__order_status='Cancelled'
    ).values('product__category__name').annotate(
        total_sales=Sum('total_price')
    ).order_by('-total_sales')
    
    # Prepare chart data
    chart_labels = []
    chart_sales = []
    chart_orders = []
    
    for item in sales_data:
        if report_type == 'daily':
            chart_labels.append(item['date'].strftime('%Y-%m-%d'))
        elif report_type == 'weekly':
            chart_labels.append(f"Week {item['date'].strftime('%U')}")
        elif report_type == 'monthly':
            chart_labels.append(item['date'].strftime('%b %Y'))
        
        chart_sales.append(float(item['total_sales']))
        chart_orders.append(item['order_count'])
    
    # Category pie chart data
    category_labels = [item['product__category__name'] or 'Unknown' for item in category_sales]
    category_data = [float(item['total_sales']) for item in category_sales]
    
    context = {
        'report_type': report_type,
        'date_range': date_range,
        'custom_start': custom_start,
        'custom_end': custom_end,
        'start_date': start_date,
        'end_date': end_date,
        'sales_data': sales_data,
        'top_products': top_products,
        'category_sales': category_sales,
        'chart_labels': json.dumps(chart_labels),
        'chart_sales': json.dumps(chart_sales),
        'chart_orders': json.dumps(chart_orders),
        'category_labels': json.dumps(category_labels),
        'category_data': json.dumps(category_data),
        'total_sales': sum(chart_sales),
        'total_orders': sum(chart_orders),
        'excel_export_available': EXCEL_EXPORT_AVAILABLE,
        'is_admin': is_admin,
        'last_end_day': last_end_day,
    }
    
    return render(request, 'posapp/reports/sales_report.html', context)


@login_required
@management_required
def export_orders_excel(request):
    """Export orders as Excel file"""
    if not EXCEL_EXPORT_AVAILABLE:
        return JsonResponse({
            'error': 'Excel export functionality requires the xlwt package. Please install it with: pip install xlwt'
        }, status=400)
        
    # Get filter parameters
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')
    status = request.GET.get('status')
    
    # Default to last 30 days if no dates provided
    today = timezone.now()
    
    try:
        # Validate start date
        if not start_date:
            start_date_obj = today - timedelta(days=30)
        else:
            try:
                # Try to parse as datetime with time first
                try:
                    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
                    # Make timezone aware
                    if timezone.is_naive(start_date_obj):
                        start_date_obj = timezone.make_aware(start_date_obj)
                except ValueError:
                    # Fall back to date only format
                    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                    # Convert to datetime at start of day
                    start_date_obj = timezone.make_aware(datetime.combine(start_date_obj, datetime.min.time()))
            except ValueError:
                return JsonResponse({
                    'error': f'Invalid start date format: {start_date}. Use YYYY-MM-DD or YYYY-MM-DD HH:MM:SS format.'
                }, status=400)
            
        # Validate end date
        if not end_date:
            end_date_obj = today
        else:
            try:
                # Try to parse as datetime with time first
                try:
                    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
                    # Make timezone aware
                    if timezone.is_naive(end_date_obj):
                        end_date_obj = timezone.make_aware(end_date_obj)
                except ValueError:
                    # Fall back to date only format
                    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                    # Convert to datetime at end of day
                    end_date_obj = timezone.make_aware(datetime.combine(end_date_obj, datetime.max.time()))
            except ValueError:
                return JsonResponse({
                    'error': f'Invalid end date format: {end_date}. Use YYYY-MM-DD or YYYY-MM-DD HH:MM:SS format.'
                }, status=400)
        
        # Validate date range
        if start_date_obj > end_date_obj:
            return JsonResponse({
                'error': 'Start date cannot be after end date.'
            }, status=400)
    
        # Filter orders using exact timestamps
        all_orders = Order.objects.filter(
            created_at__gte=start_date_obj,
            created_at__lte=end_date_obj
        )
        
        if status:
            all_orders = all_orders.filter(order_status=status)
        
        # Create workbook and add a worksheet
        workbook = xlwt.Workbook(encoding='utf-8')
        worksheet = workbook.add_sheet('Orders Report')
        
        # Styling
        header_style = xlwt.easyxf('font: bold on; align: wrap on, vert centre, horiz center; pattern: pattern solid, fore_colour light_blue;')
        title_style = xlwt.easyxf('font: bold on, height 280; align: wrap on, vert centre, horiz center;')
        date_range_style = xlwt.easyxf('font: bold on; align: wrap on, vert centre, horiz center;')
        date_style = xlwt.easyxf('font: bold off; align: wrap on, vert centre, horiz center', num_format_str='YYYY-MM-DD HH:MM:SS')
        money_style = xlwt.easyxf('font: bold off; align: horiz right', num_format_str='#,##0.00')
        total_style = xlwt.easyxf('font: bold on; align: horiz right; pattern: pattern solid, fore_colour light_green;', num_format_str='#,##0.00')
        
        # Add report title and date range
        title_row = 0
        date_range_row = 1
        header_row = 3  # Move header down to make room for title and date range
        
        # Report title
        worksheet.write_merge(title_row, title_row, 0, 11, 'Orders Report', title_style)
        
        # Date range information
        date_range_text = f'Report Period: {start_date_obj.strftime("%d %b %Y %H:%M:%S")} to {end_date_obj.strftime("%d %b %Y %H:%M:%S")}'
        if status:
            date_range_text += f' | Status: {status}'
        worksheet.write_merge(date_range_row, date_range_row, 0, 11, date_range_text, date_range_style)
        
        # Write header row
        columns = ['Order #', 'Date', 'Customer', 'Customer Phone', 'Items Count', 'Status', 'Payment Status', 'Payment Method', 'Subtotal', 'Tax', 'Discount', 'Total']
        
        for col_num, column_title in enumerate(columns):
            worksheet.write(header_row, col_num, column_title, header_style)
        
        # Write data rows
        grand_total = 0
        for row_num, order in enumerate(all_orders, 1):
            # Get the items count for this order
            items_count = order.items.count()
            
            # Adjust row index to account for header rows
            adjusted_row = row_num + header_row
            
            worksheet.write(adjusted_row, 0, order.reference_number)
            worksheet.write(adjusted_row, 1, order.created_at.strftime('%Y-%m-%d %H:%M:%S'), date_style)
            worksheet.write(adjusted_row, 2, order.customer_name or 'Walk-in Customer')
            worksheet.write(adjusted_row, 3, order.customer_phone or 'N/A')
            worksheet.write(adjusted_row, 4, items_count)
            worksheet.write(adjusted_row, 5, order.order_status)
            worksheet.write(adjusted_row, 6, order.payment_status)
            worksheet.write(adjusted_row, 7, order.payment_method)
            worksheet.write(adjusted_row, 8, float(order.subtotal), money_style)
            worksheet.write(adjusted_row, 9, float(order.tax_amount), money_style)
            worksheet.write(adjusted_row, 10, float(order.discount_amount or 0), money_style)
            worksheet.write(adjusted_row, 11, float(order.total_amount), money_style)
            
            # Only include non-cancelled orders in the total
            if order.order_status != 'Cancelled':
                grand_total += float(order.total_amount)
        
        # Write grand total row
        total_row = len(all_orders) + header_row + 2
        worksheet.write(total_row, 10, "GRAND TOTAL:", xlwt.easyxf('font: bold on; align: horiz right;'))
        worksheet.write(total_row, 11, grand_total, total_style)
        
        # Set column width
        for col_num in range(len(columns)):
            worksheet.col(col_num).width = 256 * 20  # 20 characters wide
        
        # Set up the response
        response = HttpResponse(content_type='application/ms-excel')
        filename = f"orders_report_{start_date_obj.strftime('%Y%m%d_%H%M%S')}_to_{end_date_obj.strftime('%Y%m%d_%H%M%S')}.xls"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Save workbook to response
        workbook.save(response)
        return response
        
    except Exception as e:
        return JsonResponse({
            'error': f'An error occurred while generating the Excel report: {str(e)}'
        }, status=500)


@login_required
@management_required
def export_order_items_excel(request):
    """Export order items as Excel file"""
    if not EXCEL_EXPORT_AVAILABLE:
        return JsonResponse({
            'error': 'Excel export functionality requires the xlwt package. Please install it with: pip install xlwt'
        }, status=400)
        
    # Get filter parameters
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')
    category = request.GET.get('category')
    
    # Default to last 30 days if no dates provided
    today = timezone.now()
    
    try:
        # Validate start date
        if not start_date:
            start_date_obj = today - timedelta(days=30)
        else:
            try:
                # Try to parse as datetime with time first
                try:
                    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
                    # Make timezone aware
                    if timezone.is_naive(start_date_obj):
                        start_date_obj = timezone.make_aware(start_date_obj)
                except ValueError:
                    # Fall back to date only format
                    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                    # Convert to datetime at start of day
                    start_date_obj = timezone.make_aware(datetime.combine(start_date_obj, datetime.min.time()))
            except ValueError:
                return JsonResponse({
                    'error': f'Invalid start date format: {start_date}. Use YYYY-MM-DD or YYYY-MM-DD HH:MM:SS format.'
                }, status=400)
            
        # Validate end date
        if not end_date:
            end_date_obj = today
        else:
            try:
                # Try to parse as datetime with time first
                try:
                    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
                    # Make timezone aware
                    if timezone.is_naive(end_date_obj):
                        end_date_obj = timezone.make_aware(end_date_obj)
                except ValueError:
                    # Fall back to date only format
                    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                    # Convert to datetime at end of day
                    end_date_obj = timezone.make_aware(datetime.combine(end_date_obj, datetime.max.time()))
            except ValueError:
                return JsonResponse({
                    'error': f'Invalid end date format: {end_date}. Use YYYY-MM-DD or YYYY-MM-DD HH:MM:SS format.'
                }, status=400)
        
        # Validate date range
        if start_date_obj > end_date_obj:
            return JsonResponse({
                'error': 'Start date cannot be after end date.'
            }, status=400)
    
        # Aggregate product sales data with exact timestamps
        product_sales = OrderItem.objects.filter(
            order__created_at__gte=start_date_obj,
            order__created_at__lte=end_date_obj,
            order__order_status='Completed'  # Only include completed orders
        )
        
        if category:
            product_sales = product_sales.filter(product__category_id=category)
            category_name = Category.objects.get(id=category).name
        else:
            category_name = "All Categories"
        
        # Group by product and sum quantities and totals
        product_sales = product_sales.values(
            'product__name', 
            'product__category__name'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_sales=Sum('total_price'),
            avg_unit_price=Sum('total_price') / Sum('quantity')
        ).order_by('-total_quantity')
        
        # Create workbook and add a worksheet
        workbook = xlwt.Workbook(encoding='utf-8')
        worksheet = workbook.add_sheet('Products Sold Report')
        
        # Define column widths in characters
        col_widths = [30, 20, 15, 15, 20]
        
        # Styling
        header_style = xlwt.easyxf('font: bold on; align: wrap on, vert centre, horiz center; pattern: pattern solid, fore_colour light_blue;')
        title_style = xlwt.easyxf('font: bold on, height 280; align: wrap on, vert centre, horiz center;')
        date_range_style = xlwt.easyxf('font: bold on; align: wrap on, vert centre, horiz center;')
        money_style = xlwt.easyxf('font: bold off; align: horiz right', num_format_str='#,##0.00')
        total_style = xlwt.easyxf('font: bold on; align: horiz right; pattern: pattern solid, fore_colour light_green;', num_format_str='#,##0.00')
        
        # Add report title and date range
        title_row = 0
        date_range_row = 1
        header_row = 3  # Move header down to make room for title and date range
        
        # Report title
        worksheet.write_merge(title_row, title_row, 0, 4, 'Products Sold Report', title_style)
        
        # Date range information
        date_range_text = f'Report Period: {start_date_obj.strftime("%d %b %Y %H:%M:%S")} to {end_date_obj.strftime("%d %b %Y %H:%M:%S")} | Category: {category_name}'
        worksheet.write_merge(date_range_row, date_range_row, 0, 4, date_range_text, date_range_style)
        
        # Write header row
        columns = ['Product', 'Category', 'Quantity Sold', 'Unit Price', 'Total Sales']
        
        for col_num, column_title in enumerate(columns):
            worksheet.write(header_row, col_num, column_title, header_style)
            worksheet.col(col_num).width = 256 * col_widths[col_num]  # Set column width
        
        # Write data rows
        grand_total_qty = 0
        grand_total_sales = 0
        for row_num, product in enumerate(product_sales, 1):
            # Adjust row index to account for header rows
            adjusted_row = row_num + header_row
            
            worksheet.write(adjusted_row, 0, product['product__name'])
            worksheet.write(adjusted_row, 1, product['product__category__name'] or 'Unknown')
            worksheet.write(adjusted_row, 2, product['total_quantity'])
            worksheet.write(adjusted_row, 3, float(product['avg_unit_price']), money_style)
            worksheet.write(adjusted_row, 4, float(product['total_sales']), money_style)
            
            grand_total_qty += product['total_quantity']
            grand_total_sales += float(product['total_sales'])
        
        # Write grand total row
        total_row = len(product_sales) + header_row + 2
        worksheet.write(total_row, 1, "GRAND TOTAL:", xlwt.easyxf('font: bold on; align: horiz right;'))
        worksheet.write(total_row, 2, grand_total_qty, xlwt.easyxf('font: bold on;'))
        worksheet.write(total_row, 4, grand_total_sales, total_style)
        
        # Set up the response
        response = HttpResponse(content_type='application/ms-excel')
        filename = f"products_sold_report_{start_date_obj.strftime('%Y%m%d_%H%M%S')}_to_{end_date_obj.strftime('%Y%m%d_%H%M%S')}.xls"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Save workbook to response
        workbook.save(response)
        return response
        
    except Exception as e:
        return JsonResponse({
            'error': f'An error occurred while generating the Excel report: {str(e)}'
        }, status=500)


@login_required
def sales_receipt(request):
    """Display a printable receipt for sales summary report"""
    if not (request.user.is_superuser or 
            hasattr(request.user, 'profile') and 
            hasattr(request.user.profile, 'role') and
            (request.user.profile.role.name == 'Admin' or 
            request.user.profile.role.name == 'Branch Manager')):
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')
    
    try:
        # Get date range from request
        start_date_param = request.GET.get('start_date')
        end_date_param = request.GET.get('end_date')
        
        # Set default date range to current month if not provided
        today = timezone.now()
        
        if not start_date_param or not end_date_param:
            start_date = timezone.make_aware(datetime.combine(today.replace(day=1).date(), datetime.min.time()))
            end_date = timezone.make_aware(datetime.combine(today.date(), datetime.max.time()))
        else:
            try:
                # Try to parse as datetime with time first
                try:
                    start_date = datetime.strptime(start_date_param, '%Y-%m-%d %H:%M:%S')
                    # Make timezone aware
                    if timezone.is_naive(start_date):
                        start_date = timezone.make_aware(start_date)
                except ValueError:
                    # Fall back to date only format
                    start_date = datetime.strptime(start_date_param, '%Y-%m-%d').date()
                    # Convert to datetime at start of day
                    start_date = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
                    
                # Try to parse as datetime with time first
                try:
                    end_date = datetime.strptime(end_date_param, '%Y-%m-%d %H:%M:%S')
                    # Make timezone aware
                    if timezone.is_naive(end_date):
                        end_date = timezone.make_aware(end_date)
                except ValueError:
                    # Fall back to date only format
                    end_date = datetime.strptime(end_date_param, '%Y-%m-%d').date()
                    # Convert to datetime at end of day
                    end_date = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
            except ValueError:
                # If there's any issue parsing the dates, use default values
                start_date = timezone.make_aware(datetime.combine(today.replace(day=1).date(), datetime.min.time()))
                end_date = timezone.make_aware(datetime.combine(today.date(), datetime.max.time()))
        
        # Create a cache key based on the date range
        cache_key = f"sales_receipt_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        
        # Try to get cached results
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.debug(f"Returning cached sales receipt data for {start_date} to {end_date}")
            return render(request, 'posapp/reports/sales_receipt.html', cached_data)
        
        # Get all completed orders in the date range
        completed_orders = Order.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date,
            order_status='Completed'
        )
        
        # Calculate the total sales amount with proper decimal precision
        total_sales = completed_orders.aggregate(
            total=Coalesce(Sum('total_amount'), Decimal('0.00'))
        )['total']
        
        # Calculate the total service charge amount
        total_service_charge = completed_orders.aggregate(
            total=Coalesce(Sum('service_charge_amount'), Decimal('0.00'))
        )['total']
        
        # Calculate the total paid amount
        total_paid = completed_orders.filter(
            payment_status='Paid'
        ).aggregate(
            total=Coalesce(Sum('total_amount'), Decimal('0.00'))
        )['total']
        
        # Calculate the total pending amount
        total_pending = completed_orders.filter(
            payment_status='Pending'
        ).aggregate(
            total=Coalesce(Sum('total_amount'), Decimal('0.00'))
        )['total']
        
        # Get all bill adjustments in the date range
        bill_adjustments = BillAdjustment.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        # Calculate the total bill adjustments
        total_bill_adjustments = bill_adjustments.aggregate(
            total=Coalesce(Sum('price'), Decimal('0.00'))
        )['total']
        
        # Get all advance adjustments in the date range
        advance_adjustments = AdvanceAdjustment.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        # Calculate the total advance adjustments
        total_advance_adjustments = advance_adjustments.aggregate(
            total=Coalesce(Sum('amount'), Decimal('0.00'))
        )['total']
        
        # Calculate the total adjustments
        total_adjustments = total_bill_adjustments + total_advance_adjustments
        
        # Calculate the net revenue
        net_revenue = total_sales - total_adjustments
        
        # Determine if there's a shortage
        is_shortage = net_revenue < 0
        shortage_amount = abs(net_revenue) if is_shortage else Decimal('0.00')
        
        # Get products sold in the date range
        products_sold = OrderItem.objects.filter(
            order__created_at__gte=start_date,
            order__created_at__lte=end_date,
            order__order_status='Completed'
        ).values(
            'product__name'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_sales=Sum('total_price')
        ).order_by('-total_quantity')
        
        # Prepare context data
        context = {
            'completed_orders': completed_orders,
            'total_sales': total_sales,
            'total_service_charge': total_service_charge,
            'total_paid': total_paid,
            'total_pending': total_pending,
            'bill_adjustments': bill_adjustments,
            'total_bill_adjustments': total_bill_adjustments,
            'advance_adjustments': advance_adjustments,
            'total_advance_adjustments': total_advance_adjustments,
            'total_adjustments': total_adjustments,
            'net_revenue': net_revenue,
            'is_shortage': is_shortage,
            'shortage_amount': shortage_amount,
            'products_sold': products_sold,
            'start_date': start_date,
            'end_date': end_date,
            'now': timezone.now(),
        }
        
        # Get business settings
        try:
            business_settings = get_or_create_settings([
                'business_name', 'business_address', 'business_phone', 
                'business_email', 'currency_symbol'
            ])
            
            context.update({
                'business_name': business_settings['business_name'].setting_value,
                'business_address': business_settings['business_address'].setting_value,
                'business_phone': business_settings['business_phone'].setting_value,
                'business_email': business_settings['business_email'].setting_value,
                'currency_symbol': business_settings['currency_symbol'].setting_value or 'Rs.',
            })
            
            # Get business logo from BusinessLogo model
            context['business_logo'] = BusinessLogo.get_logo_url()
        except Exception as e:
            logger.error(f"Error getting business settings: {str(e)}")
            context.update({
                'business_name': 'POS System',
                'currency_symbol': 'Rs.',
            })
        
        # Get receipt settings
        try:
            receipt_settings = get_or_create_settings([
                'receipt_header', 'receipt_footer', 'receipt_show_logo',
                'receipt_show_cashier', 'receipt_paper_size',
                'receipt_custom_css'
            ])
            
            context.update({
                'receipt_header': receipt_settings['receipt_header'].setting_value,
                'receipt_footer': receipt_settings['receipt_footer'].setting_value,
                'receipt_show_logo': receipt_settings['receipt_show_logo'].setting_value == 'True',
                'receipt_show_cashier': receipt_settings['receipt_show_cashier'].setting_value == 'True',
                'receipt_paper_size': receipt_settings['receipt_paper_size'].setting_value,
                'receipt_custom_css': receipt_settings['receipt_custom_css'].setting_value,
            })
        except Exception as e:
            logger.error(f"Error getting receipt settings: {str(e)}")
        
        # Store in cache for 1 hour (3600 seconds)
        cache.set(cache_key, context, 3600)
        
        logger.info(f"Generated sales receipt for period {start_date} to {end_date} by user {request.user.username}")
        
        return render(request, 'posapp/reports/sales_receipt.html', context)
    except Exception as e:
        logger.exception(f"Error generating sales receipt: {str(e)}")
        messages.error(request, f"An error occurred while generating the sales receipt: {str(e)}")
        return redirect('reports_dashboard')


@login_required
@management_required
def get_or_create_settings(keys, description_dict=None):
    result = {}
    for key in keys:
        try:
            setting = Setting.objects.get(setting_key=key)
        except Setting.DoesNotExist:
            # Create with default values if description_dict is provided
            if description_dict and key in description_dict:
                default_value = description_dict[key].get('default', '')
                description = description_dict[key].get('help_text', key.replace('_', ' ').title())
                setting = Setting.objects.create(
                    setting_key=key,
                    setting_value=default_value,
                    setting_description=description
                )
            else:
                setting = Setting.objects.create(
                    setting_key=key,
                    setting_value='',
                    setting_description=key.replace('_', ' ').title()
                )
        result[key] = setting
    return result


@login_required
@management_required
def sales_summary_history(request):
    """Display a list of all end-of-day sales summaries"""
    # Get all sales summaries ordered by end date (newest first)
    summaries = SalesSummary.objects.all().order_by('-end_day__end_date')
    
    # Pagination
    paginator = Paginator(summaries, 10)  # Show 10 summaries per page
    page_number = request.GET.get('page')
    summaries_page = paginator.get_page(page_number)
    
    context = {
        'summaries': summaries_page,
    }
    
    return render(request, 'posapp/reports/sales_summary_history.html', context)


@login_required
@management_required
def sales_summary_detail(request, pk):
    """Display details of a specific sales summary"""
    # Get the sales summary
    summary = get_object_or_404(SalesSummary, pk=pk)
    
    # Get business information for the receipt
    business_settings = {'business_name': 'POS System', 'business_address': '', 'business_phone': '', 'currency_symbol': 'Rs.'}
    for setting in Setting.objects.filter(
        setting_key__in=['business_name', 'business_address', 'business_phone', 'currency_symbol']
    ):
        business_settings[setting.setting_key] = setting.setting_value
    
    # Get business logo URL
    logo_url = BusinessLogo.get_logo_url()
    
    context = {
        'summary': summary,
        'business_settings': business_settings,
        'logo_url': logo_url,
        'products_sold': summary.summary_data.get('products_sold', []) if summary.summary_data else [],
    }
    
    return render(request, 'posapp/reports/sales_summary_detail.html', context) 