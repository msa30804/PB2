from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django import forms
from django.db import transaction

from ..models import Setting
from ..views.user_views import is_admin

class SettingsForm(forms.Form):
    """Base form for settings with dynamic field generation"""
    def __init__(self, *args, **kwargs):
        settings = kwargs.pop('settings', {})
        super().__init__(*args, **kwargs)
        
        # Dynamically create fields based on settings
        for key, setting_data in settings.items():
            field_type = setting_data.get('type', 'text')
            required = setting_data.get('required', True)
            choices = setting_data.get('choices', None)
            initial = setting_data.get('value', '')
            help_text = setting_data.get('help_text', '')
            
            if field_type == 'text':
                self.fields[key] = forms.CharField(
                    required=required,
                    initial=initial,
                    help_text=help_text,
                    widget=forms.TextInput(attrs={'class': 'form-control'})
                )
            elif field_type == 'textarea':
                self.fields[key] = forms.CharField(
                    required=required,
                    initial=initial,
                    help_text=help_text,
                    widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
                )
            elif field_type == 'number':
                self.fields[key] = forms.DecimalField(
                    required=required,
                    initial=initial,
                    help_text=help_text,
                    widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
                )
            elif field_type == 'checkbox':
                self.fields[key] = forms.BooleanField(
                    required=False,
                    initial=bool(initial),
                    help_text=help_text,
                )
            elif field_type == 'select' and choices:
                self.fields[key] = forms.ChoiceField(
                    choices=choices,
                    required=required,
                    initial=initial,
                    help_text=help_text,
                    widget=forms.Select(attrs={'class': 'form-control'})
                )


def get_or_create_settings(keys):
    """Get or create settings with the specified keys"""
    existing_settings = {s.setting_key: s for s in Setting.objects.filter(setting_key__in=keys)}
    
    result = {}
    for key in keys:
        if key in existing_settings:
            result[key] = existing_settings[key]
        else:
            # Create setting with empty value if it doesn't exist
            result[key] = Setting.objects.create(
                setting_key=key,
                setting_value='',
                setting_description=key.replace('_', ' ').title()
            )
    
    return result


def update_settings(settings_data):
    """Update settings in the database"""
    with transaction.atomic():
        for key, value in settings_data.items():
            setting, created = Setting.objects.get_or_create(
                setting_key=key,
                defaults={
                    'setting_value': str(value),
                    'setting_description': key.replace('_', ' ').title()
                }
            )
            
            if not created:
                setting.setting_value = str(value)
                setting.save()
    
    return True


@login_required
def settings_dashboard(request):
    """Main settings dashboard"""
    # Only allow admin users to view settings
    if not is_admin(request.user):
        messages.error(request, "You don't have permission to access settings.")
        return redirect('dashboard')
    
    # Get system information for display
    import django
    import sys
    import platform
    import socket
    from django.utils import timezone
    
    context = {
        'title': 'Settings Dashboard',
        'django_version': django.get_version(),
        'python_version': platform.python_version(),
        'server_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        'server_os': platform.platform(),
        'server_software': 'Django Development Server',
        'server_ip': socket.gethostbyname(socket.gethostname()),
    }
    
    return render(request, 'posapp/settings/dashboard.html', context)


@login_required
def business_settings(request):
    """Business information settings"""
    # Only allow admin users to edit settings
    if not is_admin(request.user):
        messages.error(request, "You don't have permission to edit settings.")
        return redirect('dashboard')
    
    # Define business settings fields
    business_settings_fields = {
        'business_name': {'type': 'text', 'required': True, 'help_text': 'Your business name'},
        'business_address': {'type': 'textarea', 'required': True, 'help_text': 'Full business address'},
        'business_phone': {'type': 'text', 'required': True, 'help_text': 'Contact phone number'},
        'business_email': {'type': 'text', 'required': False, 'help_text': 'Contact email address'},
        'business_website': {'type': 'text', 'required': False, 'help_text': 'Business website URL'},
        'business_logo': {'type': 'text', 'required': False, 'help_text': 'Logo URL or path'},
        'business_tagline': {'type': 'text', 'required': False, 'help_text': 'Your business tagline or slogan'},
    }
    
    # Get existing settings
    settings = get_or_create_settings(business_settings_fields.keys())
    
    # Prepare initial data
    initial_data = {key: settings[key].setting_value for key in business_settings_fields.keys()}
    
    # Update business settings fields with current values
    for key in business_settings_fields:
        business_settings_fields[key]['value'] = initial_data.get(key, '')
    
    if request.method == 'POST':
        form = SettingsForm(request.POST, settings=business_settings_fields)
        
        if form.is_valid():
            update_settings(form.cleaned_data)
            messages.success(request, "Business settings updated successfully.")
            return redirect('business_settings')
    else:
        form = SettingsForm(initial=initial_data, settings=business_settings_fields)
    
    context = {
        'title': 'Business Settings',
        'form': form,
        'settings_section': 'business',
    }
    
    return render(request, 'posapp/settings/form.html', context)


@login_required
def receipt_settings(request):
    """Receipt configuration settings"""
    # Only allow admin users to edit settings
    if not is_admin(request.user):
        messages.error(request, "You don't have permission to edit settings.")
        return redirect('dashboard')
    
    # Define receipt settings fields
    receipt_settings_fields = {
        'receipt_header': {'type': 'textarea', 'required': False, 'help_text': 'Text to show at the top of receipts'},
        'receipt_footer': {'type': 'textarea', 'required': False, 'help_text': 'Text to show at the bottom of receipts'},
        'receipt_show_logo': {'type': 'checkbox', 'required': False, 'help_text': 'Show business logo on receipts'},
        'receipt_show_tax': {'type': 'checkbox', 'required': False, 'help_text': 'Show tax details on receipts'},
        'receipt_show_cashier': {'type': 'checkbox', 'required': False, 'help_text': 'Show cashier name on receipts'},
        'receipt_paper_size': {
            'type': 'select', 
            'required': True, 
            'help_text': 'Paper size for receipts',
            'choices': [
                ('80mm', '80mm (Standard)'),
                ('58mm', '58mm (Compact)'),
                ('A4', 'A4 Paper'),
            ]
        },
    }
    
    # Get existing settings
    settings = get_or_create_settings(receipt_settings_fields.keys())
    
    # Prepare initial data
    initial_data = {key: settings[key].setting_value for key in receipt_settings_fields.keys()}
    
    # Update receipt settings fields with current values
    for key in receipt_settings_fields:
        receipt_settings_fields[key]['value'] = initial_data.get(key, '')
    
    if request.method == 'POST':
        form = SettingsForm(request.POST, settings=receipt_settings_fields)
        
        if form.is_valid():
            update_settings(form.cleaned_data)
            messages.success(request, "Receipt settings updated successfully.")
            return redirect('receipt_settings')
    else:
        form = SettingsForm(initial=initial_data, settings=receipt_settings_fields)
    
    context = {
        'title': 'Receipt Settings',
        'form': form,
        'settings_section': 'receipt',
    }
    
    return render(request, 'posapp/settings/form.html', context)


@login_required
def tax_settings(request):
    """Tax configuration settings"""
    # Only allow admin users to edit settings
    if not is_admin(request.user):
        messages.error(request, "You don't have permission to edit settings.")
        return redirect('dashboard')
    
    # Define tax settings fields
    tax_settings_fields = {
        'tax_rate': {'type': 'number', 'required': True, 'help_text': 'Default tax rate (%)'},
        'tax_name': {'type': 'text', 'required': True, 'help_text': 'Tax name (e.g., VAT, GST)'},
        'tax_number': {'type': 'text', 'required': False, 'help_text': 'Your business tax registration number'},
        'enable_tax': {'type': 'checkbox', 'required': False, 'help_text': 'Enable tax calculation'},
        'tax_included_in_price': {'type': 'checkbox', 'required': False, 'help_text': 'Tax is included in product prices'},
    }
    
    # Get existing settings
    settings = get_or_create_settings(tax_settings_fields.keys())
    
    # Prepare initial data
    initial_data = {key: settings[key].setting_value for key in tax_settings_fields.keys()}
    
    # Update tax settings fields with current values
    for key in tax_settings_fields:
        tax_settings_fields[key]['value'] = initial_data.get(key, '')
    
    if request.method == 'POST':
        form = SettingsForm(request.POST, settings=tax_settings_fields)
        
        if form.is_valid():
            update_settings(form.cleaned_data)
            messages.success(request, "Tax settings updated successfully.")
            return redirect('tax_settings')
    else:
        form = SettingsForm(initial=initial_data, settings=tax_settings_fields)
    
    context = {
        'title': 'Tax Settings',
        'form': form,
        'settings_section': 'tax',
    }
    
    return render(request, 'posapp/settings/form.html', context)


@login_required
def system_settings(request):
    """System configuration settings"""
    # Only allow admin users to edit settings
    if not is_admin(request.user):
        messages.error(request, "You don't have permission to edit settings.")
        return redirect('dashboard')
    
    # Define system settings fields
    system_settings_fields = {
        'currency_symbol': {'type': 'text', 'required': True, 'help_text': 'Currency symbol (e.g., $, €, £)'},
        'currency_code': {'type': 'text', 'required': True, 'help_text': 'Currency code (e.g., USD, EUR, GBP)'},
        'currency_position': {
            'type': 'select', 
            'required': True, 
            'help_text': 'Position of currency symbol',
            'choices': [
                ('before', 'Before amount (e.g., $10.00)'),
                ('after', 'After amount (e.g., 10.00$)'),
            ]
        },
        'decimal_places': {
            'type': 'select', 
            'required': True, 
            'help_text': 'Number of decimal places',
            'choices': [
                ('0', 'No decimals'),
                ('1', '1 decimal place'),
                ('2', '2 decimal places'),
                ('3', '3 decimal places'),
            ]
        },
        'low_stock_threshold': {'type': 'number', 'required': True, 'help_text': 'Alert when stock is below this value'},
        'default_order_status': {
            'type': 'select', 
            'required': True, 
            'help_text': 'Default status for new orders',
            'choices': [
                ('New', 'New'),
                ('Processing', 'Processing'),
                ('Completed', 'Completed'),
            ]
        },
    }
    
    # Get existing settings
    settings = get_or_create_settings(system_settings_fields.keys())
    
    # Prepare initial data
    initial_data = {key: settings[key].setting_value for key in system_settings_fields.keys()}
    
    # Update system settings fields with current values
    for key in system_settings_fields:
        system_settings_fields[key]['value'] = initial_data.get(key, '')
    
    if request.method == 'POST':
        form = SettingsForm(request.POST, settings=system_settings_fields)
        
        if form.is_valid():
            update_settings(form.cleaned_data)
            messages.success(request, "System settings updated successfully.")
            return redirect('system_settings')
    else:
        form = SettingsForm(initial=initial_data, settings=system_settings_fields)
    
    context = {
        'title': 'System Settings',
        'form': form,
        'settings_section': 'system',
    }
    
    return render(request, 'posapp/settings/form.html', context) 