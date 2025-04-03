from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F, DecimalField
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
import csv
import json

# Try to import xlwt, but make it optional
try:
    import xlwt
    XLWT_INSTALLED = True
except ImportError:
    XLWT_INSTALLED = False

from ..models import Order, OrderItem, Product, Category


@login_required
def reports_dashboard(request):
    """Main reports dashboard with overview of available reports"""
    
    # Get some overview stats
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Orders count (exclude cancelled orders)
    orders_today = Order.objects.filter(created_at__date=today).exclude(order_status='Cancelled').count()
    orders_week = Order.objects.filter(created_at__date__gte=week_ago).exclude(order_status='Cancelled').count()
    orders_month = Order.objects.filter(created_at__date__gte=month_ago).exclude(order_status='Cancelled').count()
    orders_total = Order.objects.exclude(order_status='Cancelled').count()
    
    # Revenue (exclude cancelled orders)
    revenue_today = Order.objects.filter(created_at__date=today).exclude(order_status='Cancelled').aggregate(total=Sum('total_amount'))['total'] or 0
    revenue_week = Order.objects.filter(created_at__date__gte=week_ago).exclude(order_status='Cancelled').aggregate(total=Sum('total_amount'))['total'] or 0
    revenue_month = Order.objects.filter(created_at__date__gte=month_ago).exclude(order_status='Cancelled').aggregate(total=Sum('total_amount'))['total'] or 0
    revenue_total = Order.objects.exclude(order_status='Cancelled').aggregate(total=Sum('total_amount'))['total'] or 0
    
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
        'xlwt_installed': XLWT_INSTALLED,
    }
    
    return render(request, 'posapp/reports/dashboard.html', context)


@login_required
def sales_report(request):
    """Sales report with charts and data"""
    
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
    
    # Get sales data excluding cancelled orders
    sales_data = Order.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
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
        order__created_at__date__gte=start_date,
        order__created_at__date__lte=end_date
    ).exclude(
        order__order_status='Cancelled'
    ).values('product__name').annotate(
        total_quantity=Sum('quantity'),
        total_sales=Sum('total_price')
    ).order_by('-total_quantity')[:10]
    
    # Sales by category (exclude orders that were cancelled)
    category_sales = OrderItem.objects.filter(
        order__created_at__date__gte=start_date,
        order__created_at__date__lte=end_date
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
        'xlwt_installed': XLWT_INSTALLED,
    }
    
    return render(request, 'posapp/reports/sales_report.html', context)


@login_required
def export_orders_excel(request):
    """Export orders as Excel file"""
    if not XLWT_INSTALLED:
        return JsonResponse({
            'error': 'Excel export functionality requires the xlwt package. Please install it with: pip install xlwt'
        }, status=400)
        
    # Get filter parameters
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')
    status = request.GET.get('status')
    
    # Default to last 30 days if no dates provided
    today = timezone.now().date()
    
    try:
        # Validate start date
        if not start_date:
            start_date_obj = today - timedelta(days=30)
        else:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({
                    'error': f'Invalid start date format: {start_date}. Use YYYY-MM-DD format.'
                }, status=400)
            
        # Validate end date
        if not end_date:
            end_date_obj = today
        else:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({
                    'error': f'Invalid end date format: {end_date}. Use YYYY-MM-DD format.'
                }, status=400)
        
        # Validate date range
        if start_date_obj > end_date_obj:
            return JsonResponse({
                'error': 'Start date cannot be after end date.'
            }, status=400)
    
        # Filter orders, exclude cancelled orders for revenue calculation
        all_orders = Order.objects.filter(
            created_at__date__gte=start_date_obj,
            created_at__date__lte=end_date_obj
        )
        
        if status:
            all_orders = all_orders.filter(order_status=status)
        
        # Create workbook and add a worksheet
        workbook = xlwt.Workbook(encoding='utf-8')
        worksheet = workbook.add_sheet('Orders Report')
        
        # Styling
        header_style = xlwt.easyxf('font: bold on; align: wrap on, vert centre, horiz center; pattern: pattern solid, fore_colour light_blue;')
        date_style = xlwt.easyxf('font: bold off; align: wrap on, vert centre, horiz center', num_format_str='YYYY-MM-DD HH:MM:SS')
        money_style = xlwt.easyxf('font: bold off; align: horiz right', num_format_str='#,##0.00')
        total_style = xlwt.easyxf('font: bold on; align: horiz right; pattern: pattern solid, fore_colour light_green;', num_format_str='#,##0.00')
        
        # Write header row
        columns = ['Order #', 'Date', 'Customer', 'Customer Phone', 'Items Count', 'Status', 'Payment Status', 'Payment Method', 'Subtotal', 'Tax', 'Discount', 'Total']
        
        for col_num, column_title in enumerate(columns):
            worksheet.write(0, col_num, column_title, header_style)
        
        # Write data rows
        grand_total = 0
        for row_num, order in enumerate(all_orders, 1):
            # Get the items count for this order
            items_count = order.items.count()
            
            worksheet.write(row_num, 0, order.order_number)
            worksheet.write(row_num, 1, order.created_at.strftime('%Y-%m-%d %H:%M:%S'), date_style)
            worksheet.write(row_num, 2, order.customer_name or 'Walk-in Customer')
            worksheet.write(row_num, 3, order.customer_phone or 'N/A')
            worksheet.write(row_num, 4, items_count)
            worksheet.write(row_num, 5, order.order_status)
            worksheet.write(row_num, 6, order.payment_status)
            worksheet.write(row_num, 7, order.payment_method)
            worksheet.write(row_num, 8, float(order.subtotal), money_style)
            worksheet.write(row_num, 9, float(order.tax_amount), money_style)
            worksheet.write(row_num, 10, float(order.discount_amount or 0), money_style)
            worksheet.write(row_num, 11, float(order.total_amount), money_style)
            
            # Only include non-cancelled orders in the total
            if order.order_status != 'Cancelled':
                grand_total += float(order.total_amount)
        
        # Write grand total row
        total_row = len(all_orders) + 2
        worksheet.write(total_row, 10, "GRAND TOTAL:", xlwt.easyxf('font: bold on; align: horiz right;'))
        worksheet.write(total_row, 11, grand_total, total_style)
        
        # Set column width
        for col_num in range(len(columns)):
            worksheet.col(col_num).width = 256 * 20  # 20 characters wide
        
        # Set up the response
        response = HttpResponse(content_type='application/ms-excel')
        filename = f"orders_report_{start_date_obj.strftime('%Y%m%d')}_to_{end_date_obj.strftime('%Y%m%d')}.xls"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Save workbook to response
        workbook.save(response)
        return response
        
    except Exception as e:
        return JsonResponse({
            'error': f'An error occurred while generating the Excel report: {str(e)}'
        }, status=500)


@login_required
def export_order_items_excel(request):
    """Export order items as Excel file"""
    if not XLWT_INSTALLED:
        return JsonResponse({
            'error': 'Excel export functionality requires the xlwt package. Please install it with: pip install xlwt'
        }, status=400)
        
    # Get filter parameters
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')
    category = request.GET.get('category')
    
    # Default to last 30 days if no dates provided
    today = timezone.now().date()
    
    try:
        # Validate start date
        if not start_date:
            start_date_obj = today - timedelta(days=30)
        else:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({
                    'error': f'Invalid start date format: {start_date}. Use YYYY-MM-DD format.'
                }, status=400)
            
        # Validate end date
        if not end_date:
            end_date_obj = today
        else:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({
                    'error': f'Invalid end date format: {end_date}. Use YYYY-MM-DD format.'
                }, status=400)
        
        # Validate date range
        if start_date_obj > end_date_obj:
            return JsonResponse({
                'error': 'Start date cannot be after end date.'
            }, status=400)
    
        # Filter order items
        items_query = OrderItem.objects.filter(
            order__created_at__date__gte=start_date_obj,
            order__created_at__date__lte=end_date_obj
        ).exclude(
            order__order_status='Cancelled'
        )
        
        if category:
            items_query = items_query.filter(product__category_id=category)
        
        # Create workbook and add a worksheet
        workbook = xlwt.Workbook(encoding='utf-8')
        worksheet = workbook.add_sheet('Items Report')
        
        # Define column widths in characters
        col_widths = [15, 10, 25, 15, 10, 15, 15, 15, 20]
        
        # Styling
        header_style = xlwt.easyxf('font: bold on; align: wrap on, vert centre, horiz center; pattern: pattern solid, fore_colour light_blue;')
        date_style = xlwt.easyxf('font: bold off; align: wrap on, vert centre, horiz center', num_format_str='YYYY-MM-DD HH:MM:SS')
        money_style = xlwt.easyxf('font: bold off; align: horiz right', num_format_str='#,##0.00')
        total_style = xlwt.easyxf('font: bold on; align: horiz right; pattern: pattern solid, fore_colour light_green;', num_format_str='#,##0.00')
        
        # Write header row
        columns = ['Order #', 'Date', 'Product', 'Category', 'Quantity', 'Unit Price', 'Total Price', 'Customer', 'Notes']
        
        for col_num, column_title in enumerate(columns):
            worksheet.write(0, col_num, column_title, header_style)
            worksheet.col(col_num).width = 256 * col_widths[col_num]  # Set column width
        
        # Write data rows
        grand_total = 0
        for row_num, item in enumerate(items_query, 1):
            worksheet.write(row_num, 0, item.order.order_number)
            worksheet.write(row_num, 1, item.order.created_at.strftime('%Y-%m-%d %H:%M:%S'), date_style)
            worksheet.write(row_num, 2, item.product.name)
            worksheet.write(row_num, 3, item.product.category.name if item.product.category else 'Unknown')
            worksheet.write(row_num, 4, item.quantity)
            worksheet.write(row_num, 5, float(item.unit_price), money_style)
            worksheet.write(row_num, 6, float(item.total_price), money_style)
            worksheet.write(row_num, 7, item.order.customer_name or 'Walk-in Customer')
            worksheet.write(row_num, 8, item.notes or '')
            
            grand_total += float(item.total_price)
        
        # Write grand total row
        total_row = len(items_query) + 2
        worksheet.write(total_row, 5, "GRAND TOTAL:", xlwt.easyxf('font: bold on; align: horiz right;'))
        worksheet.write(total_row, 6, grand_total, total_style)
        
        # Set up the response
        response = HttpResponse(content_type='application/ms-excel')
        filename = f"items_report_{start_date_obj.strftime('%Y%m%d')}_to_{end_date_obj.strftime('%Y%m%d')}.xls"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Save workbook to response
        workbook.save(response)
        return response
        
    except Exception as e:
        return JsonResponse({
            'error': f'An error occurred while generating the Excel report: {str(e)}'
        }, status=500) 