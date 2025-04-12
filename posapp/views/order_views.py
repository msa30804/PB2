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
            discount_amount = subtotal * (order.discount.value / Decimal('100.0'))
        else:
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
    """Edit an existing order."""
    order = get_object_or_404(Order, id=order_id)
    
    # Check if order is completed or cancelled and redirect if it is
    if order.order_status == 'Completed' or order.order_status == 'Cancelled':
        status = order.order_status.lower()
        messages.warning(request, f"{status.capitalize()} orders cannot be edited.")
        return redirect('order_detail', order_id=order_id)
    
    is_editable = True
    
    # Check if order is editable
    if order.payment_status == 'paid' or order.order_status == 'Completed':
        is_editable = False
        messages.warning(request, "This order cannot be fully edited because it is already paid or completed.")
    
    # Get all products and order items
    all_products = Product.objects.filter(is_available=True)
    all_order_items = OrderItem.objects.filter(order=order)
    
    # Calculate initial subtotal
    subtotal = order.get_subtotal()
    
    # Calculate discount
    discount_amount = 0
    
    if order.payment_status != 'paid' and order.discount:
        if order.discount.type == 'Percentage':
            discount_amount = (subtotal * Decimal(order.discount.value)) / 100
        elif order.discount.type == 'Fixed':
            discount_amount = Decimal(order.discount.value)
    
    # Calculate tax based on payment method
    tax_rate = Decimal('5.0') if order.payment_method.lower() == 'card' else Decimal('15.0')
    
    taxable_amount = subtotal - discount_amount
    tax_amount = (taxable_amount * tax_rate) / Decimal('100.0')
    total = taxable_amount + tax_amount
    
    # Initialize variables for temporary changes and deleted items
    deleted_items = []
    original_subtotal = subtotal
    original_total = total
    has_changes = False
    
    # Create a deep copy of order items to work with
    order_items = []
    for item in all_order_items:
        item_dict = {
            'id': item.id,
            'product': item.product,
            'quantity': item.quantity,
            'unit_price': item.unit_price,
            'total_price': item.unit_price * item.quantity,
            'original_quantity': item.quantity,
            'has_changed': False
        }
        order_items.append(item_dict)
    
    if request.method == 'POST':
        print("POST data:", request.POST)
        
        # Get the form data
        order_form = OrderForm(request.POST, instance=order)
        
        if order_form.is_valid():
            print("Form is valid")
            
            # Process item changes from the form
            item_changes = {}
            
            # Extract item changes from POST data
            for key, value in request.POST.items():
                if key.startswith('item_changes'):
                    # Parse the key format item_changes[item_id][field]
                    parts = key.replace(']', '').split('[')
                    if len(parts) == 3:
                        item_id = parts[1]
                        field = parts[2]
                        
                        if item_id not in item_changes:
                            item_changes[item_id] = {}
                        
                        if field == 'delete':
                            item_changes[item_id]['delete'] = (value.lower() == 'true')
                        elif field == 'quantity':
                            item_changes[item_id]['quantity'] = int(value)
            
            # Process new items from the form
            new_items = []
            for key, value in request.POST.items():
                if key.startswith('new_items'):
                    try:
                        new_item_data = json.loads(value)
                        new_items.append(new_item_data)
                    except json.JSONDecodeError:
                        pass
            
            # Apply changes to existing items
            for item_id, change in item_changes.items():
                try:
                    item_id = int(item_id)
                    item = OrderItem.objects.get(id=item_id, order=order)
                    
                    # Handle deleted items
                    if change.get('delete') is True:
                        item.delete()
                        print(f"Deleted item {item_id}")
                        continue
                    
                    # Handle quantity changes
                    new_quantity = change.get('quantity', 0)
                    if new_quantity <= 0:
                        item.delete()
                        print(f"Deleted item {item_id} due to zero quantity")
                    else:
                        item.quantity = new_quantity
                        item.total_price = item.unit_price * new_quantity
                        item.save()
                        print(f"Updated item {item_id} quantity to {new_quantity}")
                except OrderItem.DoesNotExist:
                    print(f"Item {item_id} not found")
            
            # Add new items
            for new_item_data in new_items:
                try:
                    product_id = new_item_data.get('product_id')
                    quantity = int(new_item_data.get('quantity', 1))
                    
                    if product_id and quantity > 0:
                        product = Product.objects.get(id=product_id)
                        OrderItem.objects.create(
                            order=order,
                            product=product,
                            quantity=quantity,
                            unit_price=product.price,
                            total_price=product.price * quantity
                        )
                        print(f"Added new item {product.name} with quantity {quantity}")
                except Exception as e:
                    print(f"Error adding new item: {str(e)}")
            
            # Save the order
            order_instance = order_form.save(commit=False)
            
            # Update subtotal, tax, and total
            updated_order = Order.objects.get(id=order_id)
            updated_subtotal = updated_order.get_subtotal()
            
            # Recalculate discount
            discount_amount = 0
            if order_instance.discount:
                if order_instance.discount.type == 'Percentage':
                    discount_amount = (updated_subtotal * Decimal(order_instance.discount.value)) / 100
                elif order_instance.discount.type == 'Fixed':
                    discount_amount = Decimal(order_instance.discount.value)
            
            # Calculate tax based on payment method
            tax_rate = Decimal('5.0') if order_instance.payment_method.lower() == 'card' else Decimal('15.0')
            
            taxable_amount = updated_subtotal - discount_amount
            tax_amount = (taxable_amount * tax_rate) / Decimal('100.0')
            total = taxable_amount + tax_amount
            
            # Update the order instance
            order_instance.subtotal = updated_subtotal
            order_instance.tax_amount = tax_amount
            order_instance.total_amount = total
            order_instance.save()
            
            messages.success(request, "Order updated successfully!")
            return redirect('order_detail', order_id=order_id)
        else:
            print("Form is invalid:", order_form.errors)
            messages.error(request, "There was an error updating the order. Please check the form and try again.")
    else:
        order_form = OrderForm(instance=order)
    
    context = {
        'form': order_form,
        'order': order,
        'products': all_products,
        'order_items': order_items,
        'deleted_items': deleted_items,
        'subtotal': subtotal,
        'discount_amount': discount_amount,
        'tax_rate': tax_rate,
        'tax_amount': tax_amount,
        'total': total,
        'original_subtotal': original_subtotal,
        'original_total': original_total,
        'has_changes': has_changes,
        'is_editable': is_editable,
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
    """Add a new item to an order temporarily until saved."""
    order = get_object_or_404(Order, id=order_id)
    
    # Check if the order is editable
    if order.order_status == 'Completed' or order.payment_status == 'paid' or order.order_status == 'Cancelled':
        status_message = 'completed or paid'
        if order.order_status == 'Cancelled':
            status_message = 'cancelled'
            
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'error', 
                'message': f'This order cannot be modified because it is already {status_message}.'
            })
        else:
            messages.error(request, f'This order cannot be modified because it is already {status_message}.')
            return redirect('order_detail', order_id=order_id)
    
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        quantity = int(request.POST.get('quantity', 1))
        
        if not product_id:
            messages.error(request, 'Please select a product.')
            return redirect('order_edit', order_id=order_id)
        
        product = get_object_or_404(Product, id=product_id)
        
        # Check if the item already exists in the order
        existing_item = OrderItem.objects.filter(order=order, product=product).first()
        
        # Temporary storage key
        temp_key = f'order_{order_id}_temp_changes'
        temp_changes = request.session.get(temp_key, {})
        
        if existing_item:
            item_id = str(existing_item.id)
            
            # If item exists, check if it's in temp changes
            if item_id in temp_changes:
                current_qty = temp_changes[item_id].get('quantity', existing_item.quantity)
                if temp_changes[item_id].get('delete') is True:
                    # Item was marked for deletion, unmark it and set new quantity
                    temp_changes[item_id] = {
                        'quantity': quantity,
                        'delete': False
                    }
                else:
                    # Update quantity
                    temp_changes[item_id] = {
                        'quantity': current_qty + quantity,
                        'delete': False
                    }
            else:
                # Item exists but not in temp changes
                temp_changes[item_id] = {
                    'quantity': existing_item.quantity + quantity,
                    'delete': False
                }
            
            message = f'Added {quantity} more of {product.name} (will be saved when you click Save Changes).'
        else:
            # This is a new item, need to create it and get its ID
            # We'll create it now but with a special flag
            new_item = OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                unit_price=product.price,
                total_price=product.price * quantity,
                is_temporary=True
            )
            
            item_id = str(new_item.id)
            temp_changes[item_id] = {
                'quantity': quantity,
                'new_item': True,  # Flag that this is a new item
                'delete': False
            }
            
            message = f'Added {quantity} of {product.name} (will be saved when you click Save Changes).'
        
        # Save changes to session
        request.session[temp_key] = temp_changes
        request.session.modified = True
        
        # Return response based on request type
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': message,
                'item_id': item_id,
                'product_name': product.name,
                'quantity': quantity,
                'unit_price': float(product.price),
                'total_price': float(product.price * quantity)
            })
        else:
            messages.success(request, message)
            return redirect('order_edit', order_id=order_id)
    
    # If not POST, redirect to order edit
    return redirect('order_edit', order_id=order_id)

@login_required
def delete_order_item(request, order_id, item_id):
    """Delete or reduce the quantity of an order item."""
    order = get_object_or_404(Order, id=order_id)
    order_item = get_object_or_404(OrderItem, id=item_id, order=order)
    
    # Check if the order is editable
    if order.order_status == 'Completed' or order.payment_status == 'paid' or order.order_status == 'Cancelled':
        status_message = 'completed or paid'
        if order.order_status == 'Cancelled':
            status_message = 'cancelled'
            
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'error', 
                'message': f'This order cannot be modified because it is already {status_message}.'
            })
        else:
            messages.error(request, f'This order cannot be modified because it is already {status_message}.')
            return redirect('order_detail', order_id=order_id)
    
    # Get the delete mode from the request
    delete_mode = request.POST.get('delete_mode', 'all')
    
    # Get reduce_by value if provided
    try:
        reduce_by = int(request.POST.get('reduce_by', 1))
    except ValueError:
        reduce_by = 1
    
    print(f"Delete order item: {item_id} from order: {order_id}")
    print(f"Delete mode: {delete_mode}")
    print(f"POST data: {request.POST}")
    print(f"Current quantity: {order_item.quantity}")
    print(f"Reduce by: {reduce_by}")
    
    # Instead of immediately updating the database, store the change in the session
    temp_key = f'order_{order_id}_temp_changes'
    temp_changes = request.session.get(temp_key, {})
    
    item_key = str(item_id)
    
    # Handle different delete modes
    if delete_mode == 'all':
        # Mark for complete deletion
        temp_changes[item_key] = {
            'delete': True
        }
        message = 'Item will be deleted when you save the order.'
        
    elif delete_mode == 'reduce':
        # If already in temp changes, adjust the quantity
        if item_key in temp_changes:
            current_quantity = temp_changes[item_key].get('quantity', order_item.quantity)
            new_quantity = max(0, current_quantity - reduce_by)
            
            if new_quantity <= 0:
                temp_changes[item_key] = {'delete': True}
                message = 'Item will be deleted when you save the order (quantity would be zero).'
            else:
                temp_changes[item_key] = {
                    'quantity': new_quantity,
                    'delete': False
                }
                message = f'Item quantity will be reduced to {new_quantity} when you save the order.'
        else:
            # Calculate the new quantity
            new_quantity = max(0, order_item.quantity - reduce_by)
            
            if new_quantity <= 0:
                temp_changes[item_key] = {'delete': True}
                message = 'Item will be deleted when you save the order (quantity would be zero).'
            else:
                temp_changes[item_key] = {
                    'quantity': new_quantity,
                    'delete': False
                }
                message = f'Item quantity will be reduced to {new_quantity} when you save the order.'
    
    # Save the changes to the session
    request.session[temp_key] = temp_changes
    request.session.modified = True
    
    print(f"Temporary changes: {temp_changes}")
    
    # Return response based on request type
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Calculate the new subtotal to return in the response
        subtotal = 0
        for item in OrderItem.objects.filter(order=order):
            # Apply temporary changes to calculate subtotal
            if str(item.id) in temp_changes:
                change = temp_changes[str(item.id)]
                if change.get('delete') is True:
                    continue  # Skip this item as it will be deleted
                quantity = change.get('quantity', item.quantity)
                subtotal += item.unit_price * quantity
            else:
                subtotal += item.unit_price * item.quantity
        
        return JsonResponse({
            'status': 'success',
            'message': message,
            'subtotal': float(subtotal),
        })
    else:
        messages.info(request, message)
        return redirect('order_edit', order_id=order_id)

@login_required
def increase_order_item(request, order_id, item_id):
    """Increase the quantity of an order item by one."""
    order = get_object_or_404(Order, id=order_id)
    order_item = get_object_or_404(OrderItem, id=item_id, order=order)
    
    # Check if order is editable
    if order.order_status == 'Completed' or order.payment_status == 'paid' or order.order_status == 'Cancelled':
        status_message = 'completed or paid'
        if order.order_status == 'Cancelled':
            status_message = 'cancelled'
            
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'error', 
                'message': f'This order cannot be modified because it is already {status_message}.'
            })
        else:
            messages.error(request, f'This order cannot be modified because it is already {status_message}.')
            return redirect('order_detail', order_id=order_id)
    
    # Instead of immediately updating the item, store the change in the session
    temp_key = f'order_{order_id}_temp_changes'
    temp_changes = request.session.get(temp_key, {})
    
    # Get current quantity from existing temp changes or from the actual item
    item_key = str(item_id)
    if item_key in temp_changes:
        # If the item was marked for deletion, unmark it
        if temp_changes[item_key].get('delete') is True:
            temp_changes[item_key]['delete'] = False
            temp_changes[item_key]['quantity'] = 1
        else:
            # Otherwise increment the quantity
            current_quantity = temp_changes[item_key].get('quantity', order_item.quantity)
            temp_changes[item_key]['quantity'] = current_quantity + 1
    else:
        # Create a new entry for this item
        temp_changes[item_key] = {
            'quantity': order_item.quantity + 1,
            'delete': False
        }
    
    # Save the changes to the session
    request.session[temp_key] = temp_changes
    request.session.modified = True
    
    print(f"Item {item_id} quantity will be increased to {temp_changes[item_key]['quantity']} when saved")
    
    # Return response based on request type
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'success', 
            'message': 'Item quantity will be increased when you save the order.',
            'new_quantity': temp_changes[item_key]['quantity']
        })
    else:
        messages.info(request, 'Item quantity will be increased when you save the order.')
        return redirect('order_edit', order_id=order_id)

def calculate_order_totals(order, save=True):
    """Calculate order totals: subtotal, discount, tax, and total"""
    # Get all order items - we need to recalculate everything from scratch
    order_items = OrderItem.objects.filter(order=order)
    
    # Calculate subtotal
    subtotal = order.get_subtotal()
    
    # Calculate discount
    discount_amount = 0
    if order.discount:
        if order.discount.type == 'Percentage':
            discount_amount = subtotal * (order.discount.value / Decimal('100.0'))
        else:
            discount_amount = order.discount.value
    
    # Calculate tax based on payment method
    tax_rate = Decimal('5.0') if order.payment_method.lower() == 'card' else Decimal('15.0')
    tax_amount = (subtotal - discount_amount) * (tax_rate / Decimal('100.0'))
    total_amount = subtotal - discount_amount + tax_amount
    
    # Update order fields if requested
    if save:
        order.subtotal = subtotal
        order.discount_amount = discount_amount
        order.tax_amount = tax_amount
        order.total_amount = total_amount
        order.save()
    
    # Return the calculated values
    return {
        'subtotal': float(subtotal),
        'discount_amount': float(discount_amount),
        'tax_amount': float(tax_amount),
        'total_amount': float(total_amount),
        # Include simple keys for Ajax responses
        'tax': float(tax_amount),
        'total': float(total_amount)
    }

def update_order_totals(order):
    """Update order totals based on items - wrapper for backwards compatibility"""
    return calculate_order_totals(order, save=True)

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
        # Complete the order without checking payment status
        order_number = order.order_number
        order.order_status = 'Completed'
        # Also set the payment status to 'Paid' when order is completed
        order.payment_status = 'Paid'
        order.save()
        messages.success(request, f'Order {order_number} has been marked as completed and paid.')
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