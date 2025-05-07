#!/usr/bin/env python
"""
Test Data Generator for POS System
---------------------------------
This script creates sample data for testing:
- 4 food-related categories
- 2 products per category with different prices and stock levels
- Some products are running items
- Some products have stock > 50
- Some products have stock < 50
"""

import os
import sys
import random
import django
from decimal import Decimal

# ========== CONFIGURATION ==========
# Set this to the absolute path of your project's root directory (where manage.py is located)
PROJECT_PATH = r"C:\Users\saqla\OneDrive\Desktop\prod\POS"
# ===================================

# Set up Django environment
sys.path.append(PROJECT_PATH)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'posproject.settings')

try:
    django.setup()
except Exception as e:
    print(f"Failed to initialize Django: {e}")
    print(f"Make sure PROJECT_PATH is set correctly: {PROJECT_PATH}")
    sys.exit(1)

# Import Django models after Django is set up
from django.db import transaction
from posapp.models import Product, Category

def create_category(name, description=None):
    """Create a category with the given name and description"""
    category = Category.objects.create(
        name=name,
        description=description or f"Description for {name}",
        is_active=True
    )
    print(f"Created category: {category.name}")
    return category

def create_product(name, category, price, cost_price, stock, is_running=False):
    """Create a product with the given attributes"""
    product = Product.objects.create(
        name=name,
        category=category,
        price=price,
        cost_price=cost_price,
        sku=f"SKU-{category.name[:3].upper()}-{random.randint(1000, 9999)}",
        stock_quantity=stock,
        is_available=True,
        is_archived=False,
        running_item=is_running,
        description=f"This is a sample {name} in the {category.name} category."
    )
    
    status = "running item" if is_running else f"stock: {stock}"
    print(f"  - Created product: {product.name} (Rs. {product.price}) [{status}]")
    return product

def generate_test_data():
    """Generate test categories and products"""
    print("Generating test data for POS system...")
    
    # Categories to create - all food related
    categories_data = [
        {"name": "Fast Food", "description": "Quick meals and snacks"},
        {"name": "Beverages", "description": "Cold and hot drinks"},
        {"name": "Desserts", "description": "Sweet treats and desserts"},
        {"name": "Main Course", "description": "Full meals and entrees"}
    ]
    
    # Create products with different configurations
    with transaction.atomic():
        # Clear any existing test data first (optional)
        # Uncomment if you want to clear data before adding new
        # Category.objects.filter(name__in=[c["name"] for c in categories_data]).delete()
        
        # Create categories and products
        for i, cat_data in enumerate(categories_data):
            category = create_category(cat_data["name"], cat_data["description"])
            
            # For each category, create 2 products
            for j in range(2):
                # Set different prices - FIX: use round() after calculating, not on float
                price_value = round(random.uniform(10, 200), 2)
                price = Decimal(str(price_value))
                cost_price = round(float(price) * 0.7, 2)
                cost_price = Decimal(str(cost_price))
                
                # Set different stock configurations based on category and product number
                if i == 0 and j == 0:  # First product in first category
                    # Running item (unlimited stock)
                    create_product(
                        f"{category.name} Special {j+1}",
                        category,
                        price,
                        cost_price,
                        0,  # Stock value doesn't matter for running items
                        is_running=True
                    )
                elif i == 1 or i == 3:  # Second or fourth category
                    # High stock (> 50)
                    stock = random.randint(51, 200)
                    create_product(
                        f"{category.name} Item {j+1}",
                        category,
                        price,
                        cost_price,
                        stock
                    )
                else:  # Other categories
                    # Low stock (< 50)
                    stock = random.randint(1, 49)
                    create_product(
                        f"{category.name} Regular {j+1}",
                        category,
                        price,
                        cost_price,
                        stock
                    )
    
    # Count created objects
    total_categories = Category.objects.count()
    total_products = Product.objects.count()
    
    print("\nSummary:")
    print(f"Total categories in database: {total_categories}")
    print(f"Total products in database: {total_products}")
    print(f"Created {len(categories_data)} categories with {len(categories_data) * 2} products")
    print("\nTest data generation completed successfully!")

if __name__ == "__main__":
    generate_test_data() 