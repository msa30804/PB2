from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from ..models import Product, Category, OrderItem
from ..forms import ProductForm
import django.db.models.deletion
from django.db import transaction

@login_required
def product_list(request):
    """Display list of all products"""
    # Get search parameters
    search_query = request.GET.get('search', '')
    category_id = request.GET.get('category', '')
    show_archived = request.GET.get('show_archived') == 'on'
    
    # Filter products based on search and category
    products = Product.objects.all().order_by('-created_at')
    
    # Filter by archived status
    if show_archived:
        # Show only archived products when toggle is on
        products = products.filter(is_archived=True)
    else:
        # Show only non-archived products when toggle is off
        products = products.filter(is_archived=False)
    
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(product_code__icontains=search_query) |
            Q(sku__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    if category_id:
        products = products.filter(category_id=category_id)
    
    # Pagination
    paginator = Paginator(products, 10)  # Show 10 products per page
    page_number = request.GET.get('page')
    products_page = paginator.get_page(page_number)
    
    categories = Category.objects.all()
    
    context = {
        'products': products_page,
        'categories': categories,
        'search_query': search_query,
        'category_id': category_id,
        'show_archived': show_archived,
    }
    
    # Check if this is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'posapp/products/product_list.html', context)
    
    return render(request, 'posapp/products/product_list.html', context)

@login_required
def product_detail(request, product_id):
    """Display details of a specific product"""
    product = get_object_or_404(Product, id=product_id)
    context = {'product': product}
    return render(request, 'posapp/products/product_detail.html', context)

@login_required
def product_create(request):
    """Create a new product"""
    # Get all categories for the form
    categories = Category.objects.all()
    
    if request.method == 'POST':
        # Get form data from request.POST
        name = request.POST.get('name')
        product_code = request.POST.get('product_code')
        category_id = request.POST.get('category')
        price = request.POST.get('price')
        sku = request.POST.get('sku') or None
        stock_quantity = request.POST.get('stock_quantity') or 0
        is_available = request.POST.get('is_available') == 'on'
        running_item = request.POST.get('running_item') == 'on'
        description = request.POST.get('description') or None
        image_file = request.FILES.get('image')
        
        # Get or create category
        category = None
        if category_id and category_id != '':
            category = get_object_or_404(Category, id=category_id)
        
        # Basic validation
        errors = {}
        if not name:
            errors['name'] = "Name is required"
        if not product_code:
            errors['product_code'] = "Product Code is required"
        elif not product_code.isdigit():
            errors['product_code'] = "Product Code must contain only numbers"
        elif Product.objects.filter(product_code=product_code).exists():
            errors['product_code'] = "Product Code already exists, must be unique"
        if not category_id:
            errors['category'] = "Category is required"
        if not price:
            errors['price'] = "Price is required"
        if not running_item and not stock_quantity:
            errors['stock_quantity'] = "Stock quantity is required for non-running items"
        
        # If no errors, create product
        if not errors:
            try:
                # If running item, set a default stock of 0 for display purposes
                if running_item and not stock_quantity:
                    stock_quantity = 0
                
                # Create product
                product = Product.objects.create(
                    name=name,
                    product_code=product_code,
                    category=category,
                    price=price,
                    sku=sku,
                    stock_quantity=stock_quantity,
                    is_available=is_available,
                    running_item=running_item,
                    description=description
                )
                
                # Set the image separately if provided
                if image_file:
                    product.set_image(image_file)
                    product.save()
                
                messages.success(request, f'Product "{product.name}" created successfully.')
                return redirect('product_detail', product_id=product.id)
            except Exception as e:
                messages.error(request, f"Error creating product: {str(e)}")
        else:
            for field, error in errors.items():
                messages.error(request, error)
    
    # Default empty context for GET request
    context = {
        'categories': categories,
        'form': {
            'instance': {}  # Empty object for template compatibility
        }
    }
    
    return render(request, 'posapp/products/product_form.html', context)

@login_required
def product_edit(request, product_id):
    """Edit an existing product"""
    product = get_object_or_404(Product, id=product_id)
    categories = Category.objects.all()
    
    if request.method == 'POST':
        # Get form data from request.POST
        name = request.POST.get('name')
        product_code = request.POST.get('product_code')
        category_id = request.POST.get('category')
        price = request.POST.get('price')
        sku = request.POST.get('sku') or None
        stock_quantity = request.POST.get('stock_quantity') or 0
        is_available = request.POST.get('is_available') == 'on'
        is_archived = request.POST.get('is_archived') == 'on'
        running_item = request.POST.get('running_item') == 'on'
        description = request.POST.get('description') or None
        image_file = request.FILES.get('image')
        
        # Check if image should be deleted
        delete_image = request.POST.get('delete_image') == 'on'
        
        # Basic validation
        errors = {}
        if not name:
            errors['name'] = "Name is required"
        if not product_code:
            errors['product_code'] = "Product Code is required"
        elif not product_code.isdigit():
            errors['product_code'] = "Product Code must contain only numbers"
        elif Product.objects.filter(product_code=product_code).exclude(id=product_id).exists():
            errors['product_code'] = "Product Code already exists, must be unique"
        if not category_id:
            errors['category'] = "Category is required"
        if not price:
            errors['price'] = "Price is required"
        if not running_item and not stock_quantity:
            errors['stock_quantity'] = "Stock quantity is required for non-running items"
            
        # If no errors, update product
        if not errors:
            # If running item, ensure stock is set properly
            if running_item and not stock_quantity:
                stock_quantity = 0
            
            # Update product
            product.name = name
            product.product_code = product_code
            if category_id and category_id != '':
                product.category = get_object_or_404(Category, id=category_id)
            else:
                product.category = None
            product.price = price
            product.sku = sku
            product.stock_quantity = stock_quantity
            product.is_available = is_available
            product.is_archived = is_archived
            product.running_item = running_item
            product.description = description
            
            # Handle image
            if delete_image:
                product.image = None
                product.image_name = None
                product.image_type = None
            elif image_file:
                product.set_image(image_file)
            
            product.save()
            messages.success(request, f'Product "{product.name}" updated successfully.')
            return redirect('product_detail', product_id=product.id)
        else:
            for field, error in errors.items():
                messages.error(request, error)
    
    # Context for both GET and error cases in POST
    context = {
        'categories': categories,
        'form': {
            'instance': product  # Pass product as the instance for the template
        }
    }
    
    return render(request, 'posapp/products/product_form.html', context)

@login_required
def product_delete(request, product_id):
    """Delete a product"""
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        # Check if product is in any pending orders
        pending_order_items = OrderItem.objects.filter(
            product=product,
            order__order_status='Pending'
        )
        
        if pending_order_items.exists():
            # If product is in pending orders, archive it instead of deleting
            product.is_available = False
            product.is_archived = True
            product.save()
            
            messages.warning(
                request, 
                f'This product cannot be deleted because it is referenced in {pending_order_items.count()} pending ' 
                f'order(s). It has been archived instead.'
            )
            return redirect('product_detail', product_id=product_id)
        
        try:
            # Find completed or cancelled order items
            completed_cancelled_items = OrderItem.objects.filter(
                product=product,
                order__order_status__in=['Completed', 'Cancelled']
            )
            
            # Store the count for the message
            item_count = completed_cancelled_items.count()
            
            # Delete the product with transaction to ensure all operations succeed or fail together
            with transaction.atomic():
                # First, delete the order items from completed/cancelled orders
                completed_cancelled_items.delete()
                
                # Now try to delete the product
                product_name = product.name
                product.delete()
                
            messages.success(request, f'Product "{product_name}" and its {item_count} references in completed/cancelled orders deleted successfully.')
            return redirect('product_list')
            
        except Exception as e:
            # If any exception occurs
            product.is_available = False
            product.is_archived = True
            product.save()
            
            messages.warning(
                request, 
                f'This product could not be deleted due to an error: {str(e)}. ' 
                f'It has been archived instead.'
            )
            return redirect('product_detail', product_id=product_id)
    
    # If not POST, redirect to the product detail page
    return redirect('product_detail', product_id=product_id)

@login_required
def product_archive(request, product_id):
    """Archive or unarchive a product"""
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        # Toggle archived status
        if product.is_archived:
            product.is_archived = False
            action_msg = "unarchived"
        else:
            product.is_archived = True
            # When archiving, also mark as unavailable
            product.is_available = False
            action_msg = "archived"
            
        product.save()
        messages.success(request, f'Product "{product.name}" {action_msg} successfully.')
        
    return redirect('product_detail', product_id=product_id)

@login_required
def check_product_stock(request, product_id):
    """API endpoint to check if a product has sufficient stock."""
    try:
        product = get_object_or_404(Product, id=product_id)
        requested_quantity = int(request.GET.get('quantity', 1))
        
        # For running items, always return true
        if product.running_item:
            return JsonResponse({
                'success': True,
                'product_id': product_id,
                'product_name': product.name,
                'running_item': True,
                'available_stock': float('inf'),  # Infinite stock
                'requested_quantity': requested_quantity,
                'available': True,
                'message': 'This is a running item with unlimited stock.'
            })
        
        # For regular items, check actual stock
        available_stock = product.stock_quantity
        is_available = product.is_available and not product.is_archived
        has_stock = available_stock >= requested_quantity
        
        return JsonResponse({
            'success': True,
            'product_id': product_id,
            'product_name': product.name,
            'running_item': False,
            'available_stock': available_stock,
            'requested_quantity': requested_quantity,
            'available': is_available and has_stock,
            'message': 'Stock check completed successfully.'
        })
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Product not found.'
        }, status=404)
    except ValueError:
        return JsonResponse({
            'success': False, 
            'message': 'Invalid quantity specified.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error checking stock: {str(e)}'
        }, status=500)

@login_required
def get_products_stock(request):
    """API endpoint to get stock information for all products."""
    try:
        # Get only relevant fields to minimize response size
        products = Product.objects.all().values('id', 'name', 'stock_quantity', 'running_item', 'is_available', 'is_archived')
        
        # Format the data for easier consumption by the frontend
        product_data = []
        for product in products:
            product_data.append({
                'id': product['id'],
                'name': product['name'],
                'stock_quantity': product['stock_quantity'],
                'running_item': product['running_item'],
                'is_available': product['is_available'] and not product['is_archived']
            })
        
        return JsonResponse({
            'success': True,
            'products': product_data
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error fetching product stocks: {str(e)}'
        }, status=500) 
