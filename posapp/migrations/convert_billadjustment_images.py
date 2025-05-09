from django.db import migrations
import os
from django.conf import settings

def convert_billadjustment_images(apps, schema_editor):
    """
    Convert existing BillAdjustmentImage images from file system to database BinaryFields
    """
    BillAdjustmentImage = apps.get_model('posapp', 'BillAdjustmentImage')
    
    # Convert BillAdjustmentImage images
    for bill_image in BillAdjustmentImage.objects.all():
        if bill_image.image and hasattr(bill_image.image, 'path'):
            try:
                image_path = bill_image.image.path
                if os.path.exists(image_path):
                    with open(image_path, 'rb') as f:
                        binary_data = f.read()
                        bill_image.image = None  # Clear ImageField reference
                        bill_image.image_name = os.path.basename(image_path)
                        bill_image.image_type = get_content_type(image_path)
                        # Set binary data directly
                        bill_image._meta.get_field('image').save_form_data(bill_image, binary_data)
                        bill_image.save()
            except Exception as e:
                print(f"Error converting bill adjustment image: {e}")

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
        ('posapp', '0031_billadjustmentimage_image_name_and_more'),
    ]

    operations = [
        migrations.RunPython(convert_billadjustment_images),
    ] 