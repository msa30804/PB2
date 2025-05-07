from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F, DecimalField
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
import csv
import json

# Try to import xlwt for Excel export, but make it optional
EXCEL_EXPORT_AVAILABLE = False
try:
    import xlwt
    EXCEL_EXPORT_AVAILABLE = True
except ImportError:
    print("xlwt not installed. Excel export will be disabled.")
except Exception as e:
    print(f"xlwt error: {e}")

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
        'excel_export_available': EXCEL_EXPORT_AVAILABLE,
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
        order__created_at__date__lte=end_date,
        order__order_status='Completed'  # Only include completed orders
    ).values('product__name', 'product__category__name').annotate(
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
        'excel_export_available': EXCEL_EXPORT_AVAILABLE,
    }
    
    return render(request, 'posapp/reports/sales_report.html', context)


@login_required
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
        date_range_text = f'Report Period: {start_date_obj.strftime("%d %b %Y")} to {end_date_obj.strftime("%d %b %Y")}'
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
            
            worksheet.write(adjusted_row, 0, order.order_number)
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
    if not EXCEL_EXPORT_AVAILABLE:
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
    
        # Aggregate product sales data
        product_sales = OrderItem.objects.filter(
            order__created_at__date__gte=start_date_obj,
            order__created_at__date__lte=end_date_obj,
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
        date_range_text = f'Report Period: {start_date_obj.strftime("%d %b %Y")} to {end_date_obj.strftime("%d %b %Y")} | Category: {category_name}'
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
        filename = f"products_sold_report_{start_date_obj.strftime('%Y%m%d')}_to_{end_date_obj.strftime('%Y%m%d')}.xls"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Save workbook to response
        workbook.save(response)
        return response
        
    except Exception as e:
        return JsonResponse({
            'error': f'An error occurred while generating the Excel report: {str(e)}'
        }, status=500) 