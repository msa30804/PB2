from django.core.management.base import BaseCommand
from posapp.models import Order
import random
import string

class Command(BaseCommand):
    help = 'Generates reference numbers for orders that do not have one'

    def handle(self, *args, **options):
        self.stdout.write('Generating reference numbers for existing orders...')
        
        # Get all orders that don't have a reference number
        orders_without_reference = Order.objects.filter(reference_number__isnull=True) | Order.objects.filter(reference_number='')
        count = orders_without_reference.count()
        
        self.stdout.write(f'Found {count} orders without reference numbers')
        
        # Keep track of used reference numbers to avoid duplicates
        existing_refs = set(Order.objects.exclude(reference_number__isnull=True).exclude(reference_number='').values_list('reference_number', flat=True))
        
        updated = 0
        for order in orders_without_reference:
            # Generate a unique reference number with format PB + 4 digits
            while True:
                # Generate random 4-digit number
                random_digits = ''.join(random.choices(string.digits, k=4))
                reference_number = f'PB{random_digits}'
                
                # Check if the reference number already exists
                if reference_number not in existing_refs:
                    order.reference_number = reference_number
                    existing_refs.add(reference_number)
                    order.save(update_fields=['reference_number'])
                    updated += 1
                    break
        
        self.stdout.write(self.style.SUCCESS(f'Successfully updated {updated} orders with new reference numbers')) 