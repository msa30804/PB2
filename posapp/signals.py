from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile, UserRole, Order, OrderItem, AuditLog, EndDay
import random
import string
from django.utils import timezone

# Create a user profile when a new user is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # Get the default role (Cashier)
        default_role, _ = UserRole.objects.get_or_create(name='Cashier')
        
        # Create a user profile
        UserProfile.objects.create(
            user=instance,
            role=default_role,
            is_active=True
        )

# Handle order number generation
@receiver(pre_save, sender=Order)
def generate_order_number(sender, instance, **kwargs):
    # Always set a proper daily order number, even if order_number exists
    # Get the last end day record
    last_end_day = EndDay.get_last_end_day()
    
    # If we have a last end day, count orders since that date
    # Otherwise count all orders for today
    if last_end_day:
        # Count orders created since the last end day
        daily_count = Order.objects.filter(created_at__gt=last_end_day.end_date).count() + 1
    else:
        # Count orders for today if no end day exists
        today = timezone.now().date()
        daily_count = Order.objects.filter(created_at__date=today).count() + 1
        
    # Set the daily order number (always set this, not just for new orders)
    instance.daily_order_number = daily_count
    
    # Generate reference number if it doesn't exist
    if not instance.reference_number:
        # Generate a unique reference number with format PB + 4 digits
        while True:
            # Generate random 4-digit number
            random_digits = ''.join(random.choices(string.digits, k=4))
            reference_number = f'PB{random_digits}'
            
            # Check if the reference number already exists
            if not Order.objects.filter(reference_number=reference_number).exists():
                instance.reference_number = reference_number
                break
    
    # Only set the persistent order number if it doesn't exist yet
    if not instance.order_number:
        # Generate the persistent unique order number (never resets)
        # Get count of existing orders and increment by 1
        order_count = Order.objects.count() + 1
        # Format as simple numeric order number
        instance.order_number = f'{order_count:05d}'

# Log user activity
@receiver(post_save, sender=User)
def log_user_activity(sender, instance, created, **kwargs):
    if created:
        AuditLog.objects.create(
            user=None,  # System activity
            action='User Created',
            entity='User',
            entity_id=instance.id,
            details=f'User {instance.username} was created'
        )
    else:
        AuditLog.objects.create(
            user=None,  # System activity
            action='User Updated',
            entity='User',
            entity_id=instance.id,
            details=f'User {instance.username} was updated'
        ) 