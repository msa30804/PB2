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
from django.db import transaction
import logging

from ..models import Order, OrderItem, Product, Setting, Category, Discount, BusinessLogo, EndDay
from ..forms import OrderForm
from ..views.settings_views import get_or_create_settings
from ..decorators import management_required

# Set up logger
logger = logging.getLogger('posapp')

@login_required
def order_list(request):
    """Display list of all orders"""
    # Get history parameter (only used by admins)
    show_history = request.GET.get('history', '0') == '1'
    
    # Use different parameter names based on whether we're showing history or not
    if show_history:
        # Parameters for history view
        search_query = request.GET.get('history_search', '')
        status_filter = request.GET.get('history_status', '')
        date_from = request.GET.get('history_date_from', '')
        date_to = request.GET.get('history_date_to', '')
    else:
        # Parameters for regular view
        search_query = request.GET.get('search', '')
        status_filter = request.GET.get('status', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
    
    # Check user roles for permissions
    is_admin = request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role.name == 'Admin')
    is_branch_manager = hasattr(request.user, 'profile') and request.user.profile.role.name == 'Branch Manager'
    
    # Get the last end day timestamp
    last_end_day = EndDay.get_last_end_day()
    last_end_day_time = last_end_day.end_date if last_end_day else None
    
    # Start with all orders for admins or branch managers, or only user's orders for regular users
    if is_admin:
        # Admins can see all orders (especially with history=1)
        if show_history:
            orders = Order.objects.all().order_by('-created_at')
        else:
            # Without history parameter, show only orders since last end day
            if last_end_day_time:
                orders = Order.objects.filter(created_at__gte=last_end_day_time).order_by('-created_at')
            else:
                orders = Order.objects.all().order_by('-created_at')
    elif is_branch_manager:
        # Branch managers can only see orders since last end day
        if last_end_day_time:
            orders = Order.objects.filter(created_at__gte=last_end_day_time).order_by('-created_at')
        else:
            orders = Order.objects.all().order_by('-created_at')
    else:
        # Regular users can only see their own orders since last end day
        if last_end_day_time:
            orders = Order.objects.filter(
                user=request.user,
                created_at__gte=last_end_day_time
            ).order_by('-created_at')
        else:
            orders = Order.objects.filter(user=request.user).order_by('-created_at')
    
    if search_query:
        # Check if the search query consists only of digits (likely a table number)
        if search_query.isdigit():
            # For numeric searches (like table numbers), use both exact and contains matching
            orders = orders.filter(
                Q(reference_number__icontains=search_query) |
                Q(customer_name__icontains=search_query) |
                Q(customer_phone__icontains=search_query) |
                Q(table_number__icontains=search_query) |
                Q(table_number__exact=search_query)  # Add exact matching for table numbers
            )
        else:
            # For text searches, use contains matching
            orders = orders.filter(
                Q(reference_number__icontains=search_query) |
                Q(customer_name__icontains=search_query) |
                Q(customer_phone__icontains=search_query) |
                Q(table_number__icontains=search_query)
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
        'is_admin': is_admin,
        'is_branch_manager': is_branch_manager,
        'show_history': show_history,
        'last_end_day': last_end_day,
    }
    
    # Check if this is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'posapp/orders/order_list.html', context)
    
    return render(request, 'posapp/orders/order_list.html', context)

@login_required
def order_detail(request, order_id):
    """Display details of a specific order"""
    order = get_object_or_404(Order, id=order_id)
    
    # Check if the user has permission to view this order
    is_admin = request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role.name == 'Admin')
    is_branch_manager = hasattr(request.user, 'profile') and request.user.profile.role.name == 'Branch Manager'
    
    if not (is_admin or is_branch_manager) and order.user != request.user:
        messages.error(request, "You don't have permission to view this order.")
        return redirect('order_list')
    
    order_items = OrderItem.objects.filter(order=order)
    
    # Calculate subtotal
    subtotal = sum(item.unit_price * item.quantity for item in order_items)
    
    # Calculate discount amount based on discount type if a discount exists
    discount_amount = 0
    if order.discount:
        if order.discount.type == 'Percentage':
            discount_amount = subtotal * (order.discount.value / Decimal('100.0'))
        else:
            discount_amount = order.discount.value
    elif order.discount_amount > 0:
        # If no discount object but there's a discount amount value
        discount_amount = order.discount_amount
    
    # Calculate tax on the discounted amount
    taxable_amount = subtotal - discount_amount
    
    # Get tax rates from settings
    business_settings = get_or_create_settings([
        'tax_rate_card', 'tax_rate_cash'
    ])
    
    # Get tax rates with fallback values
    tax_rate_card = Decimal(business_settings['tax_rate_card'].setting_value or '5.0')
    tax_rate_cash = Decimal(business_settings['tax_rate_cash'].setting_value or '15.0')
    
    # Calculate tax based on payment method
    tax_rate = tax_rate_card if order.payment_method.lower() == 'card' else tax_rate_cash
    tax_amount = (taxable_amount * tax_rate) / Decimal('100.0')
    
    # Get service charge amount
    service_charge_amount = Decimal('0.00')
    if order.order_type == 'Dine In' and order.service_charge_percent > 0:
        service_charge_amount = subtotal * (order.service_charge_percent / Decimal('100.0'))
    
    # Get delivery charges
    delivery_charges = order.delivery_charges if hasattr(order, 'delivery_charges') else Decimal('0.00')
    
    # Calculate total = subtotal - discount + tax + service charge + delivery charges
    total = taxable_amount + tax_amount + service_charge_amount + delivery_charges
    
    context = {
        'order': order,
        'order_items': order_items,
        'subtotal': subtotal,
        'discount_amount': discount_amount,
        'tax_rate': tax_rate,
        'tax_amount': tax_amount,
        'service_charge_amount': service_charge_amount,
        'delivery_charges': delivery_charges,
        'total': total,
        'is_admin': is_admin,
        'is_branch_manager': is_branch_manager,
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
            # Let the signal handler generate the order numbers
            
            # Initialize financial fields
            order.subtotal = 0
            order.tax_amount = 0
            order.discount_amount = 0
            order.total_amount = 0
            order.order_status = 'Pending'
            
            # Save order to generate ID
            order.save()
            
            # If order status is pending, update stock in database
            if order.order_status == 'Pending':
                # Set stock_already_reduced flag since we'll update it now
                order.stock_already_reduced = False
                # Update stock for all items in the order
                # Note: Since this is a new order, there won't be any items yet
                # Stock reduction will happen when items are added in order_edit
            
            messages.success(request, f'Order {order.reference_number} created successfully.')
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
    
    # Check if the user has permission to edit this order
    is_admin = request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role.name == 'Admin')
    is_branch_manager = hasattr(request.user, 'profile') and request.user.profile.role.name == 'Branch Manager'
    
    if not (is_admin or is_branch_manager) and order.user != request.user:
        messages.error(request, "You don't have permission to edit this order.")
        return redirect('order_list')
    
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
    
    # Get tax rates from settings
    business_settings = get_or_create_settings([
        'tax_rate_card', 'tax_rate_cash'
    ])
    
    # Get tax rates with fallback values
    tax_rate_card = Decimal(business_settings['tax_rate_card'].setting_value or '5.0')
    tax_rate_cash = Decimal(business_settings['tax_rate_cash'].setting_value or '15.0')
    
    # Calculate tax based on payment method
    tax_rate = tax_rate_card if order.payment_method.lower() == 'card' else tax_rate_cash
    tax_name = "Tax"
    
    taxable_amount = subtotal - discount_amount
    tax_amount = (taxable_amount * tax_rate) / Decimal('100.0')
    
    # Get delivery charges
    delivery_charges = order.delivery_charges if hasattr(order, 'delivery_charges') else Decimal('0.00')
    
    # Add delivery charges to the total
    total = taxable_amount + tax_amount + delivery_charges
    
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
            
            # Process new items
            for new_item_data in new_items:
                try:
                    product_id = new_item_data.get('product_id')
                    quantity = int(new_item_data.get('quantity', 1))
                    
                    if product_id and quantity > 0:
                        product = Product.objects.get(id=product_id)
                        
                        # Check if we need to update stock (for non-running items)
                        if order.order_status == 'Pending' and not product.running_item:
                            # Only update database stock if order is in Pending status
                            if product.stock_quantity >= quantity:
                                # Reduce stock by the exact quantity being added (no previous quantity exists)
                                product.stock_quantity -= quantity
                                product.save()
                                print(f"Reduced stock for NEW item {product.name} by {quantity}. New stock: {product.stock_quantity}")
                            else:
                                # Safety check - we shouldn't reach here due to earlier validations
                                print(f"Warning: Not enough stock for {product.name}. Available: {product.stock_quantity}, Requested: {quantity}")
                                raise ValueError(f"Not enough stock for {product.name}. Available: {product.stock_quantity}, Requested: {quantity}")
                        
                        # Create the order item
                        OrderItem.objects.create(
                            order=order,
                            product=product,
                            quantity=quantity,
                            unit_price=product.price,
                            total_price=product.price * quantity
                        )
                        print(f"Added new item {product.name} with quantity {quantity}")
                except ValueError as ve:
                    print(f"Stock error adding new item: {str(ve)}")
                    messages.error(request, str(ve))
                    continue
                except Exception as e:
                    print(f"Error adding new item: {str(e)}")
                    continue

            # Apply changes to existing items
            for item_id, change in item_changes.items():
                try:
                    item_id = int(item_id)
                    item = OrderItem.objects.get(id=item_id, order=order)
                    product = item.product
                    original_quantity = item.quantity
                    
                    # Handle deleted items
                    if change.get('delete') is True:
                        # Restore stock for non-running items if order is pending
                        if order.order_status == 'Pending':
                            if not product.running_item:
                                print(f"Restoring stock for deleted item: {product.name}, quantity: {original_quantity}")
                                product.stock_quantity += original_quantity
                                product.save()
                        
                        item.delete()
                        print(f"Deleted item {item_id}")
                        continue
                    
                    # Handle quantity changes
                    new_quantity = change.get('quantity', 0)
                    if new_quantity <= 0:
                        # Restore stock for non-running items if order is pending
                        if order.order_status == 'Pending':
                            if not product.running_item:
                                print(f"Restoring stock for zero-quantity item: {product.name}, quantity: {original_quantity}")
                                product.stock_quantity += original_quantity
                                product.save()
                        
                        item.delete()
                        print(f"Deleted item {item_id} due to zero quantity")
                    else:
                        # Calculate stock adjustment for non-running items
                        if order.order_status == 'Pending' and not product.running_item:
                            stock_difference = new_quantity - original_quantity
                            
                            if stock_difference != 0:
                                # If increasing quantity, ensure we have enough stock
                                if stock_difference > 0:
                                    # We only need to check if there's enough stock for the additional quantity (difference)
                                    if product.stock_quantity < stock_difference:
                                        raise ValueError(f"Not enough stock for {product.name}. Available: {product.stock_quantity}, Additional needed: {stock_difference}")
                                    
                                    # Reduce stock ONLY by the ADDITIONAL quantity (difference)
                                    product.stock_quantity -= stock_difference
                                    print(f"Reduced stock for {product.name} by ONLY the additional {stock_difference}. New stock: {product.stock_quantity}")
                                else:
                                    # If decreasing quantity, restore stock
                                    stock_to_restore = abs(stock_difference)
                                    product.stock_quantity += stock_to_restore
                                    print(f"Restored stock for {product.name} by {stock_to_restore}. New stock: {product.stock_quantity}")
                                
                                product.save()
                        
                        # Update the order item
                        item.quantity = new_quantity
                        item.total_price = item.unit_price * new_quantity
                        item.save()
                        print(f"Updated item {item_id} quantity to {new_quantity}")
                except ValueError as ve:
                    print(f"Stock error updating item: {str(ve)}")
                    messages.error(request, str(ve))
                    continue
                except OrderItem.DoesNotExist:
                    print(f"Item {item_id} not found")
                except Exception as e:
                    print(f"Error updating item: {str(e)}")
                    continue
            
            # Save the order
            order_instance = order_form.save(commit=False)
            
            # Process discount data from form
            discount_code = request.POST.get('discount_code', '')
            discount_type = request.POST.get('discount_type', 'fixed')
            discount_value = request.POST.get('discount_value', '0')
            discount_amount = request.POST.get('discount_amount', '0')
            discount_id = request.POST.get('discount_id', '')
            
            # Set discount fields
            order_instance.discount_code = discount_code
            order_instance.discount_type = discount_type
            order_instance.discount_value = Decimal(discount_value) if discount_value else Decimal('0')
            
            # If discount_id is provided and not empty, link to Discount object
            if discount_id and discount_id != '':
                try:
                    discount = Discount.objects.get(pk=int(discount_id))
                    order_instance.discount = discount
                except (Discount.DoesNotExist, ValueError):
                    order_instance.discount = None
            else:
                order_instance.discount = None
            
            # Update subtotal, tax, and total
            updated_subtotal = order_instance.get_subtotal()
            
            # Recalculate discount
            discount_amount = 0
            if order_instance.discount:
                if order_instance.discount.type == 'Percentage':
                    discount_amount = updated_subtotal * (order_instance.discount.value / Decimal('100.0'))
                else:
                    discount_amount = order_instance.discount.value
            # Handle manual discount when no discount object is linked
            elif discount_code == 'MANUAL' and order_instance.discount_value > 0:
                if discount_type == 'percentage':
                    discount_amount = updated_subtotal * (order_instance.discount_value / Decimal('100.0'))
                else:
                    discount_amount = order_instance.discount_value
            # If there's a discount_amount passed directly, use that
            elif Decimal(discount_amount) > 0:
                discount_amount = Decimal(discount_amount)
            
            # Calculate tax based on payment method
            tax_rate = tax_rate_card if order_instance.payment_method.lower() == 'card' else tax_rate_cash
            
            taxable_amount = updated_subtotal - discount_amount
            tax_amount = (taxable_amount * tax_rate) / Decimal('100.0')
            
            # Get delivery charges
            delivery_charges = order_instance.delivery_charges if hasattr(order_instance, 'delivery_charges') else Decimal('0.00')
            
            # Process service charge
            service_charge_percent = Decimal(request.POST.get('service_charge_percent', '0.00'))
            service_charge_amount = Decimal('0.00')
            
            # Apply service charge for Dine In orders
            if order_instance.order_type == 'Dine In' and service_charge_percent > 0:
                service_charge_amount = updated_subtotal * (service_charge_percent / Decimal('100.0'))
                
                # Update service charge fields
                order_instance.service_charge_percent = service_charge_percent
                order_instance.service_charge_amount = service_charge_amount
            else:
                # Set to zero for non-Dine In orders
                order_instance.service_charge_percent = Decimal('0.00')
                order_instance.service_charge_amount = Decimal('0.00')
            
            # Calculate total including service charge
            total = taxable_amount + tax_amount + service_charge_amount + delivery_charges
            
            # Update the order instance with the new calculated values
            order_instance.subtotal = updated_subtotal
            order_instance.discount_amount = discount_amount
            order_instance.tax_amount = tax_amount
            order_instance.total_amount = total
            
            # Debug statement to log stock status
            print(f"DEBUG: Order editing stock status - hasattr(stock_already_reduced): {hasattr(order, 'stock_already_reduced')}")
            print(f"DEBUG: Order price updates - Subtotal: {updated_subtotal}, Tax: {tax_amount}, Service Charge: {service_charge_amount}, Total: {total}")
            
            # Set status to pending and update stocks if not already done
            if order_instance.order_status == 'Pending' and not hasattr(order, 'stock_already_reduced'):
                order_instance.stock_already_reduced = True
                order_instance.save()
                # We don't need to call update_stock_on_order_pending here
                # Because we've already adjusted stock for each item individually above
                # during the processing of new items and editing existing items
            else:
                order_instance.save()
            
            messages.success(request, "Order updated successfully!")
            return redirect('order_detail', order_id=order_id)
        else:
            print("Form is invalid:", order_form.errors)
            messages.error(request, "There was an error updating the order. Please check the form and try again.")
    else:
        order_form = OrderForm(instance=order)
    
    # Get delivery charges for display in the form
    delivery_charges = order.delivery_charges if hasattr(order, 'delivery_charges') else Decimal('0.00')
    
    context = {
        'form': order_form,
        'order': order,
        'products': all_products,
        'order_items': order_items,
        'deleted_items': deleted_items,
        'subtotal': subtotal,
        'discount_amount': discount_amount,
        'tax_rate': tax_rate,
        'tax_rate_card': tax_rate_card,
        'tax_rate_cash': tax_rate_cash,
        'tax_amount': tax_amount,
        'delivery_charges': delivery_charges,
        'service_charge_percent': order.service_charge_percent if order.order_type == 'Dine In' else Decimal('0.00'),
        'service_charge_amount': order.service_charge_amount if order.order_type == 'Dine In' else Decimal('0.00'),
        'total': total,
        'original_subtotal': original_subtotal,
        'original_total': original_total,
        'has_changes': has_changes,
        'is_editable': is_editable,
    }
    
    return render(request, 'posapp/orders/order_form.html', context)

@login_required
@management_required
def order_delete(request, order_id):
    """Cancel an order instead of deleting it and restore product stock"""
    order = get_object_or_404(Order, id=order_id)
    
    # Check if order is already completed
    if order.order_status == 'Completed':
        messages.error(request, f'Order {order.reference_number} cannot be cancelled because it is already completed.')
        return redirect('order_detail', order_id=order_id)
    
    if request.method == 'POST':
        # For cancellation, check if it's already completed
        if order.order_status == 'Completed':
            messages.error(request, f'Order {order.reference_number} cannot be cancelled because it is already completed.')
            return redirect('order_detail', order_id=order_id)
        
        # Store order number for reference
        order_number = order.reference_number
        
        # Get items and their quantities for messaging
        order_items = OrderItem.objects.filter(order=order)
        stock_restored = False
        
        # Update stock levels before marking as cancelled
        if update_stock_on_order_cancelled(order):
            stock_restored = True
        
        # Mark order as cancelled
        order.order_status = 'Cancelled'
        order.save()
        
        # Display a success message with stock adjustment info if needed
        if stock_restored:
            stock_message = "Stock levels have been restored to their previous values."
            messages.success(request, f'Order {order.reference_number} has been cancelled. {stock_message}')
        else:
            messages.success(request, f'Order {order.reference_number} has been cancelled.')
        
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
    
    # Debug discount information
    print(f"DEBUG: Order #{order.reference_number} Discount Check:")
    print(f"  - Has discount object: {order.discount is not None}")
    print(f"  - discount_code: {getattr(order, 'discount_code', 'None')}")
    print(f"  - discount_type: {getattr(order, 'discount_type', 'None')}")
    print(f"  - discount_value: {getattr(order, 'discount_value', 'None')}")
    print(f"  - discount_amount: {order.discount_amount}")
    
    # Debug delivery information
    print(f"DEBUG: Order #{order.reference_number} Delivery Info:")
    print(f"  - order_type: {getattr(order, 'order_type', 'None')}")
    print(f"  - delivery_charges: {getattr(order, 'delivery_charges', 'None')}")
    print(f"  - delivery_address: {getattr(order, 'delivery_address', 'None')}")
    
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
    elif order.discount_code == 'MANUAL':
        # Handle manual discount
        discount_amount = order.discount_amount
        discount_info = {
            'name': 'Manual Discount',
            'code': 'MANUAL',
            'type': order.discount_type.capitalize() if order.discount_type else 'Fixed'
        }
        
        if order.discount_type and order.discount_type.lower() == 'percentage':
            discount_value = order.discount_value if order.discount_value else (discount_amount * 100 / subtotal)
            discount_info['value'] = f"{discount_value}%"
        else:
            discount_info['value'] = f"Rs. {discount_amount}"
    elif order.discount_amount > 0:
        # Handle legacy orders with discount_amount but no discount object
        discount_amount = order.discount_amount
        discount_info = {
            'name': 'Discount',
            'code': 'DISCOUNT',
            'type': 'Fixed',
            'value': f"Rs. {discount_amount}"
        }
    
    # Get business settings
    business_settings = get_or_create_settings([
        'business_name', 'business_address', 'business_phone', 
        'business_email', 'currency_symbol', 'tax_rate_card', 'tax_rate_cash'
    ])
    
    business_name = business_settings['business_name'].setting_value
    business_address = business_settings['business_address'].setting_value
    business_phone = business_settings['business_phone'].setting_value
    business_email = business_settings['business_email'].setting_value
    currency_symbol = business_settings['currency_symbol'].setting_value or '$'
    
    # Get tax rates from settings with fallback values
    tax_rate_card = Decimal(business_settings['tax_rate_card'].setting_value or '5.0')
    tax_rate_cash = Decimal(business_settings['tax_rate_cash'].setting_value or '15.0')
    
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
    tax_rate = tax_rate_card if order.payment_method.lower() == 'card' else tax_rate_cash
    tax_name = "Tax"
    
    # Get delivery charges
    delivery_charges = getattr(order, 'delivery_charges', Decimal('0.00'))
    
    # Set tax amount based on the calculated rate
    tax_amount = (subtotal - discount_amount) * (tax_rate / Decimal('100.0'))
    
    # Update order tax_amount and total_amount if necessary
    if order.tax_amount != tax_amount:
        order.tax_amount = tax_amount
        order.total_amount = subtotal - discount_amount + tax_amount + delivery_charges
        order.save()
    
    context = {
        'order': order,
        'order_items': order_items,
        'subtotal': subtotal,
        'discount_amount': discount_amount,
        'discount_info': discount_info,
        'tax_amount': tax_amount,
        'tax_rate': tax_rate,
        'tax_rate_card': tax_rate_card,
        'tax_rate_cash': tax_rate_cash,
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
        'currency_symbol': currency_symbol,
        'delivery_charges': delivery_charges
    }
    
    return render(request, 'posapp/orders/order_receipt.html', context)

@login_required
def kitchen_receipt(request, order_id):
    """Display a printable kitchen copy for an order
    
    Shows order details including:
    - Order reference number
    - Date and time
    - Order type (Dine In or Delivery)
    - Table number (for Dine In orders)
    - Order items with quantities
    - Order notes
    - Delivery address (for Delivery orders)
    """
    order = get_object_or_404(Order, id=order_id)
    order_items = OrderItem.objects.filter(order=order)
    
    # Get business settings
    business_settings = get_or_create_settings([
        'business_name', 'business_address', 'business_phone', 
    ])
    
    business_name = business_settings['business_name'].setting_value
    business_address = business_settings['business_address'].setting_value
    business_phone = business_settings['business_phone'].setting_value
    
    context = {
        'order': order,
        'order_items': order_items,
        'business_name': business_name,
        'business_address': business_address,
        'business_phone': business_phone,
    }
    
    return render(request, 'posapp/orders/kitchen_receipt.html', context)

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
        
        # Check if product is available and has stock (unless it's a running item)
        if not product.is_available:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error', 
                    'message': f'Product {product.name} is not available for ordering.'
                })
            else:
                messages.error(request, f'Product {product.name} is not available for ordering.')
                return redirect('order_edit', order_id=order_id)
        
        # Check stock quantity for non-running items
        if not product.running_item and product.stock_quantity <= 0:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error', 
                    'message': f'Product {product.name} is out of stock.'
                })
            else:
                messages.error(request, f'Product {product.name} is out of stock.')
                return redirect('order_edit', order_id=order_id)
                
        # Check if non-running item has enough stock for the requested quantity
        if not product.running_item and product.stock_quantity < quantity:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error', 
                    'message': f'Not enough stock available for {product.name}. Only {product.stock_quantity} available.'
                })
            else:
                messages.error(request, f'Not enough stock available for {product.name}. Only {product.stock_quantity} available.')
                return redirect('order_edit', order_id=order_id)
        
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
                    # Update quantity - check stock for non-running items
                    new_qty = current_qty + quantity
                    if not product.running_item and new_qty > (product.stock_quantity + current_qty):
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'status': 'error', 
                                'message': f'Cannot add {quantity} more of {product.name}. Stock limit reached. Available: {product.stock_quantity}'
                            })
                        else:
                            messages.error(request, f'Cannot add {quantity} more of {product.name}. Stock limit reached. Available: {product.stock_quantity}')
                            return redirect('order_edit', order_id=order_id)
                    
                    temp_changes[item_id] = {
                        'quantity': new_qty,
                        'delete': False
                    }
            else:
                # Item exists but not in temp changes
                new_qty = existing_item.quantity + quantity
                # Check stock for non-running items
                if not product.running_item and new_qty > (product.stock_quantity + existing_item.quantity):
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'status': 'error', 
                            'message': f'Cannot add {quantity} more of {product.name}. Stock limit reached. Available: {product.stock_quantity}'
                        })
                    else:
                        messages.error(request, f'Cannot add {quantity} more of {product.name}. Stock limit reached. Available: {product.stock_quantity}')
                        return redirect('order_edit', order_id=order_id)
                
                temp_changes[item_id] = {
                    'quantity': new_qty,
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
            
            # Reduce stock for non-running items
            if order.order_status == 'Pending' and not product.running_item:
                # Only update database stock for the new quantity being added
                if product.stock_quantity >= quantity:
                    product.stock_quantity -= quantity
                    product.save()
                    print(f"Reduced stock for new item {product.name} by exactly {quantity}. New stock: {product.stock_quantity}")
                else:
                    # If we don't have enough stock, delete the item and report error
                    new_item.delete()
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'status': 'error',
                            'message': f'Not enough stock available for {product.name}. Only {product.stock_quantity} available.'
                        })
                    else:
                        messages.error(request, f'Not enough stock available for {product.name}. Only {product.stock_quantity} available.')
                        return redirect('order_edit', order_id=order_id)
            
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
    
    # Update stock in database for pending orders if non-running item
    product = order_item.product
    if order.order_status == 'Pending' and not product.running_item:
        # Handle different delete modes for stock restoration
        if delete_mode == 'all':
            # Restore all stock for this item (exactly the current quantity)
            restore_quantity = order_item.quantity
            product.stock_quantity += restore_quantity
            product.save()
            print(f"Restored stock for {product.name} by exactly {restore_quantity}. New stock: {product.stock_quantity}")
        elif delete_mode == 'reduce':
            # Restore only the reduced amount (exactly the amount being reduced)
            amount_to_restore = min(reduce_by, order_item.quantity)
            product.stock_quantity += amount_to_restore
            product.save()
            print(f"Restored stock for {product.name} by exactly {amount_to_restore}. New stock: {product.stock_quantity}")
    
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
    
    # Check stock for non-running items before increasing
    product = order_item.product
    if not product.running_item:
        # Check if there's enough stock to increase by just 1 more
        if product.stock_quantity < 1:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error', 
                    'message': f'Cannot add more {product.name}. Stock limit reached. Available: {product.stock_quantity}'
                })
            else:
                messages.error(request, f'Cannot add more {product.name}. Stock limit reached. Available: {product.stock_quantity}')
                return redirect('order_edit', order_id=order_id)
            
        # Update stock in database for pending orders - reduce by exactly 1
        if order.order_status == 'Pending':
            # Reduce stock by exactly 1 (the increment amount)
            product.stock_quantity -= 1
            product.save()
            print(f"Reduced stock for {product.name} by exactly 1. New stock: {product.stock_quantity}")
    
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
    
    # Get tax rates from settings
    business_settings = get_or_create_settings([
        'tax_rate_card', 'tax_rate_cash'
    ])
    
    # Get tax rates with fallback values
    tax_rate_card = Decimal(business_settings['tax_rate_card'].setting_value or '5.0')
    tax_rate_cash = Decimal(business_settings['tax_rate_cash'].setting_value or '15.0')
    
    # Calculate tax based on payment method
    tax_rate = tax_rate_card if order.payment_method.lower() == 'card' else tax_rate_cash
    tax_name = "Tax"
    
    taxable_amount = subtotal - discount_amount
    tax_amount = (taxable_amount * tax_rate) / Decimal('100.0')
    
    # Calculate service charge for Dine In orders
    service_charge_amount = Decimal('0.00')
    if order.order_type == 'Dine In' and order.service_charge_percent > 0:
        service_charge_amount = subtotal * (order.service_charge_percent / Decimal('100.0'))
    
    # Calculate the final total including service charge and delivery charges
    delivery_charges = order.delivery_charges if hasattr(order, 'delivery_charges') else Decimal('0.00')
    total_amount = subtotal - discount_amount + tax_amount + service_charge_amount + delivery_charges
    
    # Update order fields if requested
    if save:
        order.subtotal = subtotal
        order.discount_amount = discount_amount
        order.tax_amount = tax_amount
        order.service_charge_amount = service_charge_amount
        order.total_amount = total_amount
        order.save()
    
    # Return the calculated values
    return {
        'subtotal': float(subtotal),
        'discount_amount': float(discount_amount),
        'tax_amount': float(tax_amount),
        'service_charge_amount': float(service_charge_amount),
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
    try:
        data = json.loads(request.body)
        
        # Validate service charge
        service_charge_percent = Decimal(str(data.get('service_charge_percent', '0')))
        if service_charge_percent < 0:
            return JsonResponse({'status': 'error', 'message': 'Service charge cannot be negative'}, status=400)
        if service_charge_percent > 100:
            return JsonResponse({'status': 'error', 'message': 'Service charge cannot exceed 100%'}, status=400)
        
        items = data.get('items', [])
        
        # Use atomic transaction for the entire order creation process
        with transaction.atomic():
            # Check stock availability for all items first
            for item in items:
                product_id = item['product_id']
                quantity = int(item['quantity'])
                
                # Skip stock check if stock already updated in UI
                if data.get('stock_already_reduced', False):
                    continue
                
                try:
                    product = Product.objects.select_for_update().get(id=product_id)
                    
                    # Skip stock check for running items
                    if not product.is_running and product.stock < quantity:
                        return JsonResponse({
                            'status': 'error',
                            'message': f'Insufficient stock for {product.name}. Available: {product.stock}',
                            'product_id': product_id
                        }, status=400)
                except Product.DoesNotExist:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Product with ID {product_id} does not exist',
                    }, status=400)
            
            # Extract customer info
            customer_name = data.get('customer_name', '')
            customer_phone = data.get('customer_phone', '')
            
            # Get order data
            subtotal = Decimal(str(data.get('subtotal', '0')))
            tax_amount = Decimal(str(data.get('tax_amount', '0')))
            discount_amount = Decimal(str(data.get('discount_amount', '0')))
            discount_code = data.get('discount_code', '')
            discount_type = data.get('discount_type', '')
            discount_value = data.get('discount_value', 0)
            
            # Service charge (only for Dine In with subtotal >= 1000)
            order_type = data.get('order_type', 'Take Away')
            service_charge_percent = Decimal('0.00')
            service_charge_amount = Decimal('0.00')
            
            if order_type == 'Dine In' and subtotal >= 1000:
                service_charge_percent = Decimal(str(data.get('service_charge_percent', '0')))
                service_charge_amount = subtotal * (service_charge_percent / Decimal('100.0'))
            
            # Delivery charges (only for Delivery)
            delivery_charges = Decimal('0.00')
            if order_type == 'Delivery':
                delivery_charges = Decimal(str(data.get('delivery_charges', '0')))
            
            # Calculate total amount
            total_amount = subtotal - discount_amount + tax_amount + service_charge_amount + delivery_charges
            
            # Check if a non-manual discount code was used
            discount = None
            if discount_code and discount_code != 'MANUAL':
                try:
                    discount = Discount.objects.get(code=discount_code, is_active=True)
                except Discount.DoesNotExist:
                    # If discount code doesn't exist, still create the order but without linking to a discount
                    pass
            
            # Create order
            order = Order.objects.create(
                customer_name=customer_name,
                customer_phone=customer_phone,
                subtotal=subtotal,
                tax_amount=tax_amount,
                discount_amount=discount_amount,
                discount_code=discount_code,
                discount_type=discount_type,
                discount_value=Decimal(str(discount_value)) if discount_value else Decimal('0'),
                discount=discount,  # Link to discount object if found
                service_charge_percent=service_charge_percent,
                service_charge_amount=service_charge_amount,
                delivery_charges=delivery_charges,
                total_amount=total_amount,
                payment_method=data.get('payment_method', 'Cash'),
                payment_status=data.get('payment_status', 'Pending'),
                order_status=data.get('order_status', 'Pending'),
                notes=data.get('notes', ''),
                user=request.user if request.user.is_authenticated else None,
                order_type=order_type,
                delivery_address=data.get('delivery_address', ''),
                table_number=data.get('table_number', '')
            )
            
            # Create order items
            for item_data in items:
                product_id = item_data['product_id']
                quantity = int(item_data['quantity'])
                unit_price = Decimal(str(item_data['unit_price']))
                total_price = Decimal(str(item_data['total_price']))
                
                OrderItem.objects.create(
                    order=order,
                    product_id=product_id,
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=total_price
                )
                
                # Update product stock if not already updated in UI
                if not data.get('stock_already_reduced', False):
                    try:
                        product = Product.objects.get(id=product_id)
                        if not product.is_running:
                            product.stock -= quantity
                            product.save()
                    except Product.DoesNotExist:
                        # Log error but don't fail the order creation
                        logger.error(f"Failed to update stock for product ID {product_id} - product not found")
            
            logger.info(f"Order #{order.id} created successfully by {request.user.username if request.user.is_authenticated else 'anonymous'}")
            
            # Calculate display number (daily order number)
            today = timezone.localtime(timezone.now()).date()
            daily_count = Order.objects.filter(created_at__date=today).count()
            
            # Return success response
            return JsonResponse({
                'status': 'success',
                'order_id': order.id,
                'reference_number': order.reference_number,
                'display_number': f'{daily_count}'
            })
    except Exception as e:
        logger.exception(f"Error creating order: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'An unexpected error occurred while creating the order.',
            'details': str(e)
        }, status=500)

def update_stock_on_order_pending(order):
    """
    Update product stock quantities in the database when an order is set to pending.
    This ensures consistency between UI and database stock values.
    Skip running_item products as they don't have stock reduced.
    """
    # Check if stock reduction was already handled by the UI (from POS screen)
    # We still want to update the database even if UI has already updated the visual stock
    order_items = OrderItem.objects.filter(order=order)
    
    for item in order_items:
        # Reduce stock by the ordered quantity (negative change)
        adjust_stock(item, -item.quantity, is_initial_order=True)
    
    return True

def update_stock_on_order_complete(order):
    """
    Update product stock quantities when an order is completed.
    Skip running_item products (they don't have their stock reduced).
    """
    # Check if stock reduction was already handled by the UI (from POS screen)
    # or by the update_stock_on_order_pending function
    if hasattr(order, 'stock_already_reduced') and order.stock_already_reduced:
        return True
        
    order_items = OrderItem.objects.filter(order=order)
    
    for item in order_items:
        # Reduce stock by the ordered quantity (negative change)
        adjust_stock(item, -item.quantity)
    
    return True

def adjust_stock(order_item, quantity_change, is_cancelled=False, is_initial_order=False):
    """
    Helper function to adjust stock for an order item.
    
    Parameters:
    - order_item: The OrderItem instance
    - quantity_change: Amount to change stock by (positive to add back to stock, negative to reduce stock)
    - is_cancelled: Whether this adjustment is due to order cancellation
    - is_initial_order: Whether this is the initial order creation
    
    Returns True if successful, False if failed
    """
    product = order_item.product
    
    # Skip running items - they don't have their stock managed
    if product.running_item:
        return True
        
    # For stock reduction (negative quantity_change), ensure we have enough stock
    if quantity_change < 0 and product.stock_quantity < abs(quantity_change):
        print(f"Not enough stock for {product.name}. Available: {product.stock_quantity}, Needed: {abs(quantity_change)}")
        return False
    
    # Adjust the stock
    old_stock = product.stock_quantity
    product.stock_quantity += quantity_change
    product.save()
    
    # Log the adjustment
    if is_cancelled:
        print(f"Order cancelled: Restored {quantity_change} stock for {product.name}. Old: {old_stock}, New: {product.stock_quantity}")
    elif is_initial_order:
        print(f"Initial order: Reduced stock for {product.name} by {abs(quantity_change)}. Old: {old_stock}, New: {product.stock_quantity}")
    else:
        action = "added" if quantity_change > 0 else "reduced"
        print(f"Order edited: {action} {abs(quantity_change)} stock for {product.name}. Old: {old_stock}, New: {product.stock_quantity}")
    
    return True

def update_stock_on_order_cancelled(order):
    """
    Restore product stock quantities when an order is cancelled.
    Skip running_item products (they don't have their stock managed).
    Returns True if stock was restored, False if any issues occurred.
    
    This ensures that when an order is cancelled, the original inventory is restored
    based on the quantity that was in the order. For example:
    1. Initial stock = 80
    2. Order 6 items = 74 left
    3. Cancel order = Back to 80
    """
    try:
        # Only restore stock for previously non-cancelled orders
        if order.order_status != 'Cancelled':
            order_items = OrderItem.objects.filter(order=order)
            
            for item in order_items:
                product = item.product
                
                # Skip running items - they don't have their stock managed
                if product.running_item:
                    continue
                
                # Add the item quantity back to stock
                product.stock_quantity += item.quantity
                product.save()
                
                print(f"Order cancelled: Restored {item.quantity} stock for {product.name}. New stock: {product.stock_quantity}")
        
        return True
    except Exception as e:
        print(f"Error restoring stock on order cancellation: {str(e)}")
        return False

@login_required
def complete_order(request, order_id):
    """Mark an order as completed"""
    order = get_object_or_404(Order, id=order_id)
    
    # If the order is already completed, show a warning message
    if order.order_status == 'Completed':
        messages.warning(request, f'Order {order.reference_number} is already completed.')
        return redirect('order_list')
    
    # Cancelled orders cannot be completed
    if order.order_status == 'Cancelled':
        messages.warning(request, f'Cancelled orders cannot be completed. Order {order.reference_number} remains cancelled.')
        return redirect('order_detail', order_id=order_id)
    
    if request.method == 'POST':
        # Check for the UI stock reduction flag from request
        stock_already_reduced = request.POST.get('stock_already_reduced') == 'true'
        
        # Complete the order without checking payment status
        order_number = order.reference_number
        
        # Set stock_already_reduced attribute if needed
        if stock_already_reduced:
            order.stock_already_reduced = True
        
        # Update product stock quantities if needed
        update_stock_on_order_complete(order)
        
        # Update the order status
        order.order_status = 'Completed'
        # Also set the payment status to 'Paid' when order is completed
        order.payment_status = 'Paid'
        order.save()
        
        messages.success(request, f'Order {order.reference_number} has been marked as completed and paid.')
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

@login_required
@csrf_exempt
def get_active_tables(request):
    """
    Return a list of tables that currently have pending orders assigned to them.
    This helps prevent assigning multiple orders to the same table.
    """
    active_tables = Order.objects.filter(
        order_type='Dine In', 
        order_status='Pending',
        table_number__isnull=False
    ).exclude(table_number='').values_list('table_number', flat=True).distinct()
    
    # Convert to a list
    active_tables_list = list(active_tables)
    
    return JsonResponse({
        'active_tables': active_tables_list
    }) 