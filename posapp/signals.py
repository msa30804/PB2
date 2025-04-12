from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile, UserRole, Order, OrderItem, AuditLog
import random
import string

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
    if not instance.order_number:
        # Generate order number with format pbmsa0003XXXXX
        # Get count of existing orders and increment by 1
        order_count = Order.objects.count() + 1
        # Format as pbmsa0003XXXXX where XXXXX is the incremented count
        instance.order_number = f'pbmsa0003{order_count:05d}'

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