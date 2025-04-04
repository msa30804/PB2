from .models import Setting

def settings_processor(request):
    """Context processor to make settings available in all templates"""
    settings_dict = {}
    
    # Get core settings used in most pages
    core_settings = [
        'business_name',
        'currency_symbol',
        'currency_position',
        'tax_rate',
        'enable_tax',
    ]
    
    # Get settings from database
    for key in core_settings:
        settings_dict[key] = Setting.get_value(key, default='')
    
    # Process currency symbol and position for easier use in templates
    currency_symbol = settings_dict.get('currency_symbol', '$')
    currency_position = settings_dict.get('currency_position', 'before')
    
    # Add helper function for formatting currency
    def format_currency(amount):
        if currency_position == 'before':
            return f"{currency_symbol}{amount}"
        else:
            return f"{amount}{currency_symbol}"
    
    settings_dict['format_currency'] = format_currency
    
    return {'settings': settings_dict} 