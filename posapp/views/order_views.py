from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.utils import timezone
from django.http import JsonResponse
# Comment out WeasyPrint import for now since we're using HTML display
# from weasyprint import HTML
from django.template.loader import render_to_string
from django.http import HttpResponse
import tempfile
import datetime
import uuid
import json
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from ..models import Order, OrderItem, Product
from ..forms import OrderForm

@login_required
def order_list(request):
    """Display list of all orders"""
    # Get search parameters
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Filter orders based on search and status
    orders = Order.objects.all().order_by('-created_at')
    
    if search_query:
        orders = orders.filter(
            Q(customer_name__icontains=search_query) | 
            Q(customer_phone__icontains=search_query) |
            Q(order_number__icontains=search_query)
        )
    
    if status_filter:
        orders = orders.filter(order_status=status_filter)
    
    if date_from:
        date_from_obj = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
        orders = orders.filter(created_at__date__gte=date_from_obj)
    
    if date_to:
        date_to_obj = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
        orders = orders.filter(created_at__date__lte=date_to_obj)
    
    # Pagination
    paginator = Paginator(orders, 10)  # Show 10 orders per page
    page_number = request.GET.get('page')
    orders_page = paginator.get_page(page_number)
    
    context = {
        'orders': orders_page,
        'search_query': search_query,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'order_status_choices': Order.ORDER_STATUS_CHOICES,
    }
    
    # Check if this is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'posapp/orders/order_list.html', context)
    
    return render(request, 'posapp/orders/order_list.html', context)

@login_required
def order_detail(request, order_id):
    """Display details of a specific order"""
    order = get_object_or_404(Order, id=order_id)
    order_items = OrderItem.objects.filter(order=order)
    
    # Calculate subtotal and total
    subtotal = sum(item.unit_price * item.quantity for item in order_items)
    
    # Calculate discount amount based on discount type if a discount exists
    discount_amount = 0
    if order.discount:
        if order.discount.type == 'Percentage':
            discount_amount = subtotal * (order.discount.value / 100)
        else:  # fixed amount
            discount_amount = order.discount.value
    
    total = subtotal - discount_amount
    
    context = {
        'order': order,
        'order_items': order_items,
        'subtotal': subtotal,
        'discount_amount': discount_amount,
        'total': total,
    }
    
    return render(request, 'posapp/orders/order_detail.html', context)

@login_required
def order_create(request):
    """Create a new order"""
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.user = request.user
            order.order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
            
            # Initialize financial fields
            order.subtotal = 0
            order.tax_amount = 0
            order.discount_amount = 0
            order.total_amount = 0
            
            order.save()
            messages.success(request, f'Order {order.order_number} created successfully.')
            return redirect('order_edit', order_id=order.id)
    else:
        form = OrderForm()
    
    context = {
        'form': form,
        'title': 'Create New Order',
    }
    
    return render(request, 'posapp/orders/order_form.html', context)

@login_required
def order_edit(request, order_id):
    """Edit an existing order"""
    order = get_object_or_404(Order, id=order_id)
    order_items = OrderItem.objects.filter(order=order)
    
    if request.method == 'POST':
        form = OrderForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(request, f'Order {order.order_number} updated successfully.')
            return redirect('order_detail', order_id=order.id)
    else:
        form = OrderForm(instance=order)
    
    # Get all products for the product selector
    products = Product.objects.filter(is_available=True)
    
    # Calculate totals
    subtotal = sum(item.unit_price * item.quantity for item in order_items)
    
    # Initialize discount_amount to prevent UnboundLocalError
    discount_amount = 0
    
    # Apply discount if present
    if order.discount:
        if order.discount.type == 'Percentage':
            discount_amount = subtotal * (order.discount.value / 100)
        else:  # Fixed amount
            discount_amount = order.discount.value
        
        # Update the order with discount information
        order.discount_amount = discount_amount
    
    total = subtotal - discount_amount
    
    context = {
        'form': form,
        'order': order,
        'order_items': order_items,
        'products': products,
        'subtotal': subtotal,
        'discount_amount': discount_amount,
        'total': total,
        'title': f'Edit Order {order.order_number}',
    }
    
    return render(request, 'posapp/orders/order_form.html', context)

@login_required
def order_delete(request, order_id):
    """Cancel an order instead of deleting it"""
    order = get_object_or_404(Order, id=order_id)
    
    # Check if order is already completed
    if order.order_status == 'Completed':
        messages.error(request, f'Order {order.order_number} cannot be cancelled because it is already completed.')
        return redirect('order_detail', order_id=order_id)
    
    if request.method == 'POST':
        order_number = order.order_number
        order.order_status = 'Cancelled'
        order.save()
        messages.success(request, f'Order {order.order_number} has been cancelled.')
        return redirect('order_list')
    
    return redirect('order_detail', order_id=order_id)

@login_required
def order_receipt(request, order_id):
    """Generate a receipt for an order"""
    order = get_object_or_404(Order, id=order_id)
    order_items = OrderItem.objects.filter(order=order)
    
    # Calculate subtotal
    subtotal = sum(item.unit_price * item.quantity for item in order_items)
    
    # Calculate discount amount based on discount type if a discount exists
    discount_amount = 0
    if hasattr(order, 'discount') and order.discount:
        if order.discount.type == 'Percentage':
            discount_amount = subtotal * (order.discount.value / 100)
        else:  # fixed amount
            discount_amount = order.discount.value
    
    total = subtotal - discount_amount
    
    context = {
        'order': order,
        'order_items': order_items,
        'subtotal': subtotal,
        'discount_amount': discount_amount,
        'total': total,
        'today': timezone.now(),
        'company_name': 'Your POS System',
        'company_address': '123 Main Street, City, Country',
        'company_phone': '+1234567890',
        'company_email': 'contact@yourpos.com',
        'barcode_image': '',  # Placeholder for barcode image
    }
    
    # Render the receipt as HTML
    html_string = render_to_string('posapp/orders/order_receipt.html', context)
    
    # For direct viewing in browser (HTML response)
    return HttpResponse(html_string)

@login_required
def add_order_item(request, order_id):
    """Add an item to an order via AJAX"""
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id)
        
        try:
            product_id = request.POST.get('product_id')
            quantity = int(request.POST.get('quantity', 1))
            unit_price = float(request.POST.get('unit_price', 0))
            
            # Validate inputs
            if not product_id or quantity <= 0 or unit_price <= 0:
                return JsonResponse({'error': 'Invalid input data'}, status=400)
            
            # Get the product
            product = get_object_or_404(Product, id=product_id)
            
            # Create the order item
            order_item = OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                unit_price=unit_price,
                total_price=quantity * unit_price
            )
            
            # Update order totals
            update_order_totals(order)
            
            return JsonResponse({
                'success': True,
                'item_id': order_item.id,
                'message': f'Added {quantity} x {product.name}'
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
def delete_order_item(request, order_id, item_id):
    """Delete an item from an order via AJAX"""
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id)
        order_item = get_object_or_404(OrderItem, id=item_id, order=order)
        
        try:
            # Delete the order item
            order_item.delete()
            
            # Update order totals
            update_order_totals(order)
            
            return JsonResponse({
                'success': True,
                'message': 'Item removed successfully'
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

def update_order_totals(order):
    """Helper function to update order totals"""
    # Calculate subtotal
    order_items = OrderItem.objects.filter(order=order)
    subtotal = sum(item.quantity * item.unit_price for item in order_items)
    
    # Set discount amount based on discount type if a discount exists
    discount_amount = 0
    if hasattr(order, 'discount') and order.discount:
        if order.discount.type == 'Percentage':
            discount_amount = subtotal * (order.discount.value / 100)
        else:  # fixed amount
            discount_amount = order.discount.value
    
    # Update order fields
    order.subtotal = subtotal
    order.discount_amount = discount_amount
    order.total_amount = subtotal - discount_amount
    
    # Save the order
    order.save()

@login_required
@csrf_exempt  # For simplicity in this example - consider proper CSRF protection in production
@require_POST
def create_order_api(request):
    """Create a new order from POS via AJAX"""
    try:
        # Parse JSON data from request body
        data = json.loads(request.body)
        
        # Create order
        payment_status = data.get('payment_status', 'Pending')
        order_status = 'Pending'  # Default status is Pending
        
        order = Order(
            order_number=f"ORD-{uuid.uuid4().hex[:8].upper()}",
            user=request.user,
            customer_name=data.get('customer_name', ''),
            customer_phone=data.get('customer_phone', ''),
            subtotal=data.get('subtotal', 0),
            tax_amount=data.get('tax_amount', 0),
            discount_amount=data.get('discount_amount', 0),
            total_amount=data.get('total_amount', 0),
            payment_method=data.get('payment_method', 'Cash'),
            payment_status=payment_status,
            order_status=order_status,
            notes=data.get('notes', '')
        )
        order.save()
        
        # Create order items
        for item_data in data.get('items', []):
            product = get_object_or_404(Product, id=item_data.get('product_id'))
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=item_data.get('quantity', 1),
                unit_price=item_data.get('unit_price', 0),
                total_price=item_data.get('total_price', 0)
            )
        
        # Update product inventory (decrease stock)
        for item_data in data.get('items', []):
            product = Product.objects.get(id=item_data.get('product_id'))
            if product.stock_quantity is not None:  # Only update if stock is tracked
                new_stock = product.stock_quantity - item_data.get('quantity', 0)
                product.stock_quantity = max(0, new_stock)  # Prevent negative stock
                product.save()
                
        # Return success response with order ID
        return JsonResponse({'status': 'success', 'order_id': order.order_number})
    
    except Exception as e:
        # Return error response
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def complete_order(request, order_id):
    """Mark an order as completed"""
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        # Check if payment status is 'Paid' before allowing completion
        if order.payment_status != 'Paid':
            messages.error(request, f'Order {order.order_number} cannot be completed until payment is marked as paid.')
            return redirect('order_detail', order_id=order_id)
            
        order_number = order.order_number
        order.order_status = 'Completed'
        order.save()
        messages.success(request, f'Order {order_number} has been marked as completed.')
        return redirect('order_list')
    
    return redirect('order_detail', order_id=order_id)

@login_required
def mark_order_paid(request, order_id):
    """Mark an order as paid"""
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        order_number = order.order_number
        order.payment_status = 'Paid'
        
        # Ensure order status is Pending unless it's already Completed or Cancelled
        if order.order_status != 'Completed' and order.order_status != 'Cancelled':
            order.order_status = 'Pending'
            
        order.save()
        messages.success(request, f'Order {order_number} has been marked as paid.')
        return redirect('order_list')
    
    return redirect('order_detail', order_id=order_id) 