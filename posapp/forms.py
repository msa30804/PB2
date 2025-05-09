from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import (
    UserProfile, UserRole, Category, Product, 
    Order, OrderItem, Discount, Setting, BusinessLogo
)

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Username',
        'id': 'id_username',
        'autocomplete': 'username',
        'aria-label': 'Username'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Password',
        'id': 'id_password',
        'autocomplete': 'current-password',
        'aria-label': 'Password'
    }))

class UserForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        self.fields['password1'].widget = forms.PasswordInput(attrs={'class': 'form-control'})
        self.fields['password2'].widget = forms.PasswordInput(attrs={'class': 'form-control'})

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ('phone', 'role', 'is_active')
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ('name', 'description')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class ProductForm(forms.ModelForm):
    """Form for Product model"""
    image = forms.ImageField(required=False, widget=forms.FileInput(attrs={'class': 'form-control'}))
    
    class Meta:
        model = Product
        fields = ('name', 'product_code', 'category', 'price', 'sku', 'stock_quantity', 'is_available', 'running_item', 'description')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'product_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter unique product code'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'sku': forms.TextInput(attrs={'class': 'form-control'}),
            'stock_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'running_item': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        
    def clean_product_code(self):
        """Validate that product_code is unique and numeric"""
        product_code = self.cleaned_data.get('product_code')
        
        # Check if it's numeric
        if not product_code.isdigit():
            raise forms.ValidationError("Product code must contain only numbers.")
        
        # Check uniqueness (excluding current instance if editing)
        product_id = self.instance.id if self.instance else None
        if Product.objects.filter(product_code=product_code).exclude(id=product_id).exists():
            raise forms.ValidationError("This product code is already in use. Please use a different code.")
            
        return product_code
    
    def save(self, commit=True):
        product = super().save(commit=False)
        
        # Handle the image field separately
        image = self.cleaned_data.get('image')
        if image:
            product.set_image(image)
        
        if commit:
            product.save()
            
        return product

class OrderForm(forms.ModelForm):
    customer_name = forms.CharField(
        max_length=100, 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Customer Name'})
    )
    customer_phone = forms.CharField(
        max_length=20, 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Customer Phone'})
    )
    
    class Meta:
        model = Order
        fields = ('customer_name', 'customer_phone', 'notes')
        widgets = {
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Order Notes'}),
        }

class OrderItemForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ('product', 'quantity', 'unit_price', 'notes')
        widgets = {
            'product': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class DiscountForm(forms.ModelForm):
    class Meta:
        model = Discount
        fields = ('name', 'code', 'type', 'value', 'is_active', 'start_date', 'end_date')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'type': forms.Select(attrs={'class': 'form-control'}),
            'value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
    
    def clean_code(self):
        code = self.cleaned_data.get('code')
        
        # Skip validation if code is empty
        if not code:
            return code
            
        # Check if the code already exists
        discount_id = self.instance.id if self.instance else None
        if Discount.objects.filter(code=code).exclude(id=discount_id).exists():
            raise forms.ValidationError("This discount code is already in use. Please use a different code.")
            
        return code

class SettingForm(forms.ModelForm):
    class Meta:
        model = Setting
        fields = ('setting_value', 'setting_description')
        widgets = {
            'setting_value': forms.TextInput(attrs={'class': 'form-control'}),
            'setting_description': forms.TextInput(attrs={'class': 'form-control'}),
        }

class BusinessLogoForm(forms.ModelForm):
    """Form for uploading a business logo"""
    image = forms.ImageField(
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        help_text='Upload a small logo image (recommended size: 200x100 pixels)',
        label='Business Logo'
    )
    
    class Meta:
        model = BusinessLogo
        fields = []  # Don't include any fields from the model
        
    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            # Check file size (limit to 500KB)
            if image.size > 500 * 1024:
                raise forms.ValidationError("Image file size must be under 500KB")
            # Check image dimensions here if needed
        return image
    
    def save(self, commit=True):
        logo = super().save(commit=False)
        
        # Handle the image field
        image = self.cleaned_data.get('image')
        if image:
            logo.set_image(image)
        
        if commit:
            logo.save()
            
        return logo 