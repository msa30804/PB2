from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from ..models import Product, Category
from ..forms import ProductForm

@login_required
def product_list(request):
    """Display list of all products"""
    # Get search parameters
    search_query = request.GET.get('search', '')
    category_id = request.GET.get('category', '')
    
    # Filter products based on search and category
    products = Product.objects.all().order_by('-created_at')
    
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) | 
            Q(barcode__icontains=search_query) | 
            Q(sku__icontains=search_query)
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
    }
    
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
        category_id = request.POST.get('category')
        price = request.POST.get('price')
        cost_price = request.POST.get('cost_price') or None
        barcode = request.POST.get('barcode') or None
        sku = request.POST.get('sku') or None
        stock_quantity = request.POST.get('stock_quantity')
        is_available = request.POST.get('is_available') == 'on'
        description = request.POST.get('description') or None
        
        # Handle image upload
        image = request.FILES.get('image')
        
        # Basic validation
        errors = {}
        if not name:
            errors['name'] = "Name is required"
        if not category_id:
            errors['category'] = "Category is required"
        if not price:
            errors['price'] = "Price is required"
        if not stock_quantity:
            errors['stock_quantity'] = "Stock quantity is required"
        
        # If no errors, create product
        if not errors:
            try:
                # Get category object
                category = Category.objects.get(id=category_id)
                
                # Create product
                product = Product.objects.create(
                    name=name,
                    category=category,
                    price=price,
                    cost_price=cost_price,
                    barcode=barcode,
                    sku=sku,
                    stock_quantity=stock_quantity,
                    is_available=is_available,
                    description=description,
                    image=image
                )
                
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
        category_id = request.POST.get('category')
        price = request.POST.get('price')
        cost_price = request.POST.get('cost_price') or None
        barcode = request.POST.get('barcode') or None
        sku = request.POST.get('sku') or None
        stock_quantity = request.POST.get('stock_quantity')
        is_available = request.POST.get('is_available') == 'on'
        description = request.POST.get('description') or None
        
        # Check if image should be deleted
        delete_image = request.POST.get('delete_image')
        
        # Handle image upload
        image = request.FILES.get('image')
        
        # Basic validation
        errors = {}
        if not name:
            errors['name'] = "Name is required"
        if not category_id:
            errors['category'] = "Category is required"
        if not price:
            errors['price'] = "Price is required"
        if not stock_quantity:
            errors['stock_quantity'] = "Stock quantity is required"
        
        # If no errors, update product
        if not errors:
            try:
                # Get category object
                category = Category.objects.get(id=category_id)
                
                # Update product fields
                product.name = name
                product.category = category
                product.price = price
                product.cost_price = cost_price
                product.barcode = barcode
                product.sku = sku
                product.stock_quantity = stock_quantity
                product.is_available = is_available
                product.description = description
                
                # Handle image
                if delete_image and product.image:
                    product.image.delete(save=False)
                    product.image = None
                
                if image:
                    if product.image:
                        product.image.delete(save=False)
                    product.image = image
                
                product.save()
                messages.success(request, f'Product "{product.name}" updated successfully.')
                return redirect('product_detail', product_id=product.id)
            except Exception as e:
                messages.error(request, f"Error updating product: {str(e)}")
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
        product_name = product.name
        product.delete()
        messages.success(request, f'Product "{product_name}" deleted successfully.')
        return redirect('product_list')
    
    # If not POST, redirect to the product detail page
    return redirect('product_detail', product_id=product_id) 