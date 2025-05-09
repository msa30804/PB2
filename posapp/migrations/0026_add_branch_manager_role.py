from django.db import migrations

def add_branch_manager_role(apps, schema_editor):
    UserRole = apps.get_model('posapp', 'UserRole')
    # Check if Branch Manager role already exists
    if not UserRole.objects.filter(name='Branch Manager').exists():
        UserRole.objects.create(
            name='Branch Manager',
            description='Can access POS, view all orders, and generate reports'
        )

def remove_branch_manager_role(apps, schema_editor):
    UserRole = apps.get_model('posapp', 'UserRole')
    UserRole.objects.filter(name='Branch Manager').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('posapp', '0025_alter_order_discount_code_alter_order_discount_type_and_more'),
    ]

    operations = [
        migrations.RunPython(add_branch_manager_role, remove_branch_manager_role),
    ] 