from django.db import migrations
import os
from django.conf import settings

def convert_images_to_database(apps, schema_editor):
    """
    Convert existing images from file system to database BinaryFields
    """
    Product = apps.get_model('posapp', 'Product')
    BusinessLogo = apps.get_model('posapp', 'BusinessLogo')
    
    # Convert Product images
    for product in Product.objects.all():
        if product.image and hasattr(product.image, 'path'):
            try:
                image_path = product.image.path
                if os.path.exists(image_path):
                    with open(image_path, 'rb') as f:
                        binary_data = f.read()
                        product.image = None  # Clear ImageField reference
                        product.image_name = os.path.basename(image_path)
                        product.image_type = get_content_type(image_path)
                        # Set binary data directly
                        product._meta.get_field('image').save_form_data(product, binary_data)
                        product.save()
            except Exception as e:
                print(f"Error converting product image: {e}")
    
    # Convert BusinessLogo images
    for logo in BusinessLogo.objects.all():
        if logo.image and hasattr(logo.image, 'path'):
            try:
                image_path = logo.image.path
                if os.path.exists(image_path):
                    with open(image_path, 'rb') as f:
                        binary_data = f.read()
                        logo.image = None  # Clear ImageField reference
                        logo.image_name = os.path.basename(image_path)
                        logo.image_type = get_content_type(image_path)
                        # Set binary data directly
                        logo._meta.get_field('image').save_form_data(logo, binary_data)
                        logo.save()
            except Exception as e:
                print(f"Error converting logo image: {e}")
    
    # We'll handle BillAdjustmentImage in a separate migration after it's created

def get_content_type(file_path):
    """
    Determine content type based on file extension
    """
    extension = os.path.splitext(file_path)[1].lower()
    
    content_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.webp': 'image/webp',
    }
    
    return content_types.get(extension, 'image/jpeg')

class Migration(migrations.Migration):

    dependencies = [
        ('posapp', '0027_advanceadjustment_billadjustment'),
    ]

    operations = [
        migrations.RunPython(convert_images_to_database),
    ] 