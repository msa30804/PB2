from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.utils import timezone
from django.http import JsonResponse
# PDF export is disabled
PDF_EXPORT_AVAILABLE = False
from django.template.loader import render_to_string
from django.http import HttpResponse
import tempfile
import datetime
import uuid
import json
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from decimal import Decimal
from django.urls import reverse

from ..models import Order, OrderItem, Product, Setting, Category, Discount, BusinessLogo
from ..forms import OrderForm
from ..views.settings_views import get_or_create_settings

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
    order = get_object_or_404(Order, id=order_id)
    order_items = OrderItem.objects.filter(order=order)

    # Check if the order is editable (not paid and not completed)
    is_editable = order.payment_status != 'Paid' and order.order_status != 'Completed'
    
    print(f"Order edit request for order {order_id}, method: {request.method}")
    print(f"Order is_editable: {is_editable}")
    
    if request.method == 'POST':
        form = OrderForm(request.POST, instance=order)
        
        # Print debug information
        print("POST data received:")
        for key, value in request.POST.items():
            print(f"{key}: {value}")
        
        print(f"Original customer_name: {order.customer_name}")
        print(f"Original customer_phone: {order.customer_phone}")
        
        # Check if this is the form submission, not an AJAX call for items
        if 'submit_order' in request.POST:
            print("Processing order form submission")
            
            if form.is_valid():
                print("Form is valid")
                # Update customer information directly from form data
                order.customer_name = request.POST.get('customer_name', order.customer_name)
                order.customer_phone = request.POST.get('customer_phone', order.customer_phone)
                order.notes = request.POST.get('notes', order.notes)
                
                # Save the order
                order.save()
                print(f"Order saved with customer_name: {order.customer_name}, customer_phone: {order.customer_phone}")
                
                # Redirect to the order detail page
                return JsonResponse({'status': 'success', 'redirect_url': reverse('order_list')})
            else:
                print("Form errors:", form.errors)
                return JsonResponse({'status': 'error', 'message': 'Invalid form data'})
    else:
        form = OrderForm(instance=order)

    products = Product.objects.filter(is_available=True)
    context = {
        'order': order,
        'form': form,
        'products': products,
        'order_items': order_items,
        'is_editable': is_editable,
        'add_url': reverse('add_order_item', args=[order_id]),
        'delete_url': reverse('delete_order_item', kwargs={'order_id': order_id, 'item_id': 0}).replace('/0', ''),
        'title': f'Edit Order {order.order_number}'
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
    """Display a printable receipt for an order"""
    order = get_object_or_404(Order, id=order_id)
    order_items = OrderItem.objects.filter(order=order)
    
    # Calculate subtotal and discount amount
    subtotal = sum([item.unit_price * item.quantity for item in order_items])
    discount_amount = 0
    discount_info = None
    
    if order.discount:
        # Create discount info dictionary
        discount_info = {
            'name': order.discount.name,
            'code': order.discount.code,
            'type': order.discount.type
        }
        
        if order.discount.type == 'Percentage':
            discount_amount = subtotal * (order.discount.value / Decimal('100.0'))
            discount_info['value'] = f"{order.discount.value}%"
        else:
            discount_amount = order.discount.value
            discount_info['value'] = f"Rs. {order.discount.value}"
    
    # Get business settings
    business_settings = get_or_create_settings([
        'business_name', 'business_address', 'business_phone', 
        'business_email', 'currency_symbol'
    ])
    
    business_name = business_settings['business_name'].setting_value
    business_address = business_settings['business_address'].setting_value
    business_phone = business_settings['business_phone'].setting_value
    business_email = business_settings['business_email'].setting_value
    currency_symbol = business_settings['currency_symbol'].setting_value or '$'
    
    # Get business logo from BusinessLogo model
    business_logo = BusinessLogo.get_logo_url()
    
    # Get receipt settings
    receipt_settings = get_or_create_settings([
        'receipt_header', 'receipt_footer', 'receipt_show_logo',
        'receipt_show_cashier', 'receipt_paper_size',
        'receipt_custom_css'
    ])
    
    receipt_header = receipt_settings['receipt_header'].setting_value
    receipt_footer = receipt_settings['receipt_footer'].setting_value
    receipt_show_logo = receipt_settings['receipt_show_logo'].setting_value == 'True'
    receipt_show_cashier = receipt_settings['receipt_show_cashier'].setting_value == 'True'
    receipt_paper_size = receipt_settings['receipt_paper_size'].setting_value
    receipt_custom_css = receipt_settings['receipt_custom_css'].setting_value
    
    # Calculate tax based on payment method
    tax_rate = Decimal('5.0') if order.payment_method.lower() == 'card' else Decimal('15.0')
    tax_name = "Tax"
    
    # Set tax amount based on the calculated rate
    tax_amount = (subtotal - discount_amount) * (tax_rate / Decimal('100.0'))
    
    # Update order tax_amount and total_amount if necessary
    if order.tax_amount != tax_amount:
        order.tax_amount = tax_amount
        order.total_amount = subtotal - discount_amount + tax_amount
        order.save()
    
    context = {
        'order': order,
        'order_items': order_items,
        'subtotal': subtotal,
        'discount_amount': discount_amount,
        'discount_info': discount_info,
        'tax_amount': tax_amount,
        'tax_rate': tax_rate,
        'tax_name': tax_name,
        'business_name': business_name,
        'business_address': business_address,
        'business_phone': business_phone,
        'business_email': business_email,
        'business_logo': business_logo,
        'receipt_header': receipt_header,
        'receipt_footer': receipt_footer,
        'receipt_show_logo': receipt_show_logo,
        'receipt_show_cashier': receipt_show_cashier,
        'receipt_paper_size': receipt_paper_size,
        'receipt_custom_css': receipt_custom_css,
        'currency_symbol': currency_symbol
    }
    
    return render(request, 'posapp/orders/order_receipt.html', context)

@login_required
def add_order_item(request, order_id):
    """Add an item to an existing order via AJAX"""
    order = get_object_or_404(Order, id=order_id)
    
    # Check if order is editable
    if order.order_status == 'Completed' or order.payment_status == 'Paid':
        return JsonResponse({
            'status': 'error',
            'message': 'Cannot modify a completed or paid order'
        })
    
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        quantity = request.POST.get('quantity')
        
        try:
            # Validate inputs
            if not product_id or not quantity:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Product and quantity are required'
                })
            
            product = get_object_or_404(Product, id=product_id)
            quantity = int(quantity)
            
            if quantity <= 0:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Quantity must be greater than 0'
                })
            
            # Check if this product is already in the order
            existing_item = OrderItem.objects.filter(order=order, product=product).first()
            
            if existing_item:
                # Update quantity of existing item
                existing_item.quantity += quantity
                existing_item.total_price = existing_item.unit_price * existing_item.quantity
                existing_item.save()
                
                is_new_item = False
                item_id = existing_item.id
                new_quantity = existing_item.quantity
            else:
                # Create new order item
                new_item = OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    unit_price=product.price,
                    total_price=product.price * quantity
                )
                
                is_new_item = True
                item_id = new_item.id
                new_quantity = quantity
            
            # Update order totals
            update_order_totals(order)
            
            # Get order data for the response
            order_data = {
                'subtotal': float(order.subtotal),
                'discount_amount': float(order.discount_amount) if order.discount_amount else 0,
                'tax_amount': float(order.tax_amount),
                'total_amount': float(order.total_amount)
            }
            
            return JsonResponse({
                'status': 'success',
                'message': 'Item added to order',
                'is_new_item': is_new_item,
                'item_id': item_id,
                'new_quantity': new_quantity,
                'order_data': order_data
            })
            
        except Product.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Product not found'
            })
        except ValueError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid quantity'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request'
    })

@login_required
def delete_order_item(request, order_id, item_id):
    """Delete an item from an order via AJAX"""
    order = get_object_or_404(Order, id=order_id)
    
    # Check if order is editable
    if order.order_status == 'Completed' or order.payment_status == 'Paid':
        return JsonResponse({
            'status': 'error',
            'message': 'Cannot modify a completed or paid order'
        })
    
    if request.method == 'POST':
        try:
            # Get the order item
            order_item = get_object_or_404(OrderItem, id=item_id, order=order)
            
            # Delete the order item
            order_item.delete()
            
            # Update order totals
            update_order_totals(order)
            
            # Get order data for the response
            order_data = {
                'subtotal': float(order.subtotal),
                'discount_amount': float(order.discount_amount) if order.discount_amount else 0,
                'tax_amount': float(order.tax_amount),
                'total_amount': float(order.total_amount)
            }
            
            return JsonResponse({
                'status': 'success',
                'message': 'Item removed from order',
                'order_data': order_data
            })
            
        except OrderItem.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Order item not found'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request'
    })

def update_order_totals(order):
    """Calculate and update order totals"""
    # Calculate subtotal from order items
    subtotal = Decimal('0.0')
    for item in order.items.all():
        subtotal += item.total_price
    
    # Set discount amount based on discount type if a discount exists
    discount_amount = Decimal('0.0')
    if order.discount:
        if order.discount.type == 'Percentage':
            discount_amount = subtotal * (order.discount.value / Decimal('100.0'))
        else:  # fixed amount
            discount_amount = order.discount.value
    
    # Calculate tax based on payment method (5% for card, 15% for others)
    tax_rate = Decimal('5.0') if order.payment_method.lower() == 'card' else Decimal('15.0')
    tax_amount = (subtotal - discount_amount) * (tax_rate / Decimal('100.0'))
    
    # Update order fields
    order.subtotal = subtotal
    order.discount_amount = discount_amount
    order.tax_amount = tax_amount
    order.total_amount = subtotal - discount_amount + tax_amount
    
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
        payment_method = data.get('payment_method', 'Cash')
        
        # Calculate subtotal, discount, and tax - convert everything to Decimal
        subtotal = Decimal(str(data.get('subtotal', 0)))
        discount_amount = Decimal(str(data.get('discount_amount', 0)))
        
        # Get discount if code is provided
        discount = None
        discount_code = data.get('discount_code')
        if discount_code:
            try:
                discount = Discount.objects.get(code=discount_code, is_active=True)
            except Discount.DoesNotExist:
                pass  # Ignore if discount doesn't exist
        
        # Calculate tax based on payment method (5% for card, 15% for others)
        tax_rate = Decimal('5.0') if payment_method.lower() == 'card' else Decimal('15.0')
        tax_amount = (subtotal - discount_amount) * (tax_rate / Decimal('100.0'))
        total_amount = subtotal - discount_amount + tax_amount
        
        order = Order(
            order_number=f"ORD-{uuid.uuid4().hex[:8].upper()}",
            user=request.user,
            customer_name=data.get('customer_name', ''),
            customer_phone=data.get('customer_phone', ''),
            discount=discount,  # Store the discount object
            subtotal=subtotal,
            tax_amount=tax_amount,
            discount_amount=discount_amount,
            total_amount=total_amount,
            payment_method=payment_method,
            payment_status=payment_status,
            order_status=order_status,
            notes=data.get('notes', '')
        )
        order.save()
        
        # Create order items
        items_data = data.get('items', [])
        for item_data in items_data:
            product = Product.objects.get(id=item_data.get('product_id'))
            quantity = int(item_data.get('quantity', 1))
            unit_price = Decimal(str(item_data.get('unit_price', item_data.get('price', product.price))))
            total_price = Decimal(str(quantity)) * unit_price
            
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                unit_price=unit_price,
                total_price=total_price,
                notes=item_data.get('notes', '')
            )
        
        # Success response with order details
        return JsonResponse({
            'success': True,
            'order_id': order.id,
            'order_number': order.order_number,
            'total_amount': float(order.total_amount),
            'message': f'Order {order.order_number} created successfully!'
        })
    
    except Exception as e:
        print(f"General error in create_order_api: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error creating order: {str(e)}'
        }, status=400)

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
    order = get_object_or_404(Order, pk=order_id)
    order.payment_status = 'Paid'
    
    # If order is not already Completed or Cancelled, set it to Pending
    if order.order_status not in ['Completed', 'Cancelled']:
        order.order_status = 'Pending'
    
    order.save()
    messages.success(request, "Order marked as paid!")
    
    return redirect('order_detail', order_id=order_id) 