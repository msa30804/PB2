#!/usr/bin/env python
"""
Database Reset Script
--------------------
This standalone script deletes all data from the POS database except users.
It can be run from anywhere, not just within the project directory.

Usage:
    python reset_database.py

Make sure to set the PROJECT_PATH variable to your project's root directory
before running this script.
"""

import os
import sys
import django

# ========== CONFIGURATION ==========
# Set this to the absolute path of your project's root directory (where manage.py is located)
PROJECT_PATH = r"C:\Users\H.A.R\Desktop\POS"
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
from django.contrib.auth.models import User
from posapp.models import (
    Product, Category, Order, OrderItem, Discount, 
    Setting, PaymentTransaction, AuditLog, BusinessLogo,
    BusinessSettings, UserProfile, UserRole
)

def delete_model_data(model, model_name):
    """Delete all records from a specific model and report the count"""
    try:
        count = model.objects.all().count()
        model.objects.all().delete()
        print(f'✓ Deleted {count} {model_name}')
        return count
    except Exception as e:
        print(f'✗ Error deleting {model_name}: {e}')
        return 0

def main():
    print('=' * 60)
    print('DATABASE RESET TOOL')
    print('=' * 60)
    print('This will delete ALL data from the database EXCEPT users and user roles.')
    print('Products, orders, categories, and all other data will be permanently deleted.')
    print('This action CANNOT be undone!')
    print('=' * 60)
    
    confirm = input('Type "DELETE ALL DATA" to confirm: ')
    
    if confirm != 'DELETE ALL DATA':
        print('\nOperation cancelled. No data was deleted.')
        return
    
    print('\nDeleting all data...\n')
    
    try:
        with transaction.atomic():
            total_deleted = 0
            
            # Delete data in a specific order to respect foreign key constraints
            total_deleted += delete_model_data(OrderItem, "Order Items")
            total_deleted += delete_model_data(PaymentTransaction, "Payment Transactions")
            total_deleted += delete_model_data(Order, "Orders")
            total_deleted += delete_model_data(Product, "Products")
            total_deleted += delete_model_data(Category, "Categories")
            total_deleted += delete_model_data(Discount, "Discounts")
            total_deleted += delete_model_data(Setting, "Settings")
            total_deleted += delete_model_data(AuditLog, "Audit Logs")
            total_deleted += delete_model_data(BusinessLogo, "Business Logos")
            total_deleted += delete_model_data(BusinessSettings, "Business Settings")
            
            print('\nSummary:')
            print(f'Total records deleted: {total_deleted}')
            user_count = User.objects.count()
            print(f'User accounts preserved: {user_count}')
        
        print('\n✓ Database reset completed successfully!')
        print('The POS system has been reset to its initial state with user accounts preserved.')
        
    except Exception as e:
        print(f'\n✗ Error during database reset: {e}')
        print('Database may be in an inconsistent state. Check your application to ensure it works correctly.')

if __name__ == '__main__':
    main() 