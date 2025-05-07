from django.contrib import admin
from .models import (
    UserRole, UserProfile, Category, Product, 
    Order, OrderItem, Discount, Setting,
    PaymentTransaction, AuditLog, BusinessLogo,
    BusinessSettings
)

@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name', 'description')

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'role', 'is_active', 'created_at')
    list_filter = ('is_active', 'role')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'phone')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'stock_quantity', 'is_available', 'is_archived')
    list_filter = ('category', 'is_available', 'is_archived', 'running_item')
    search_fields = ('name', 'sku', 'description')

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('created_at',)

class PaymentTransactionInline(admin.TabularInline):
    model = PaymentTransaction
    extra = 0
    readonly_fields = ('created_at',)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'user', 'customer_name', 'total_amount', 'payment_method', 'payment_status', 'order_status', 'created_at')
    list_filter = ('payment_status', 'order_status', 'payment_method', 'created_at')
    search_fields = ('order_number', 'customer_name', 'customer_phone', 'notes')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [OrderItemInline, PaymentTransactionInline]

@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'type', 'value', 'is_active', 'start_date', 'end_date')
    list_filter = ('type', 'is_active', 'start_date', 'end_date')
    search_fields = ('name', 'code')

@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ('setting_key', 'setting_value', 'setting_description', 'updated_at')
    search_fields = ('setting_key', 'setting_value', 'setting_description')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'entity', 'entity_id', 'ip_address', 'created_at')
    list_filter = ('entity', 'created_at')
    search_fields = ('action', 'details', 'user__username')
    readonly_fields = ('created_at',)

@admin.register(BusinessSettings)
class BusinessSettingsAdmin(admin.ModelAdmin):
    list_display = ('business_name', 'tax_rate_card', 'tax_rate_cash', 'updated_at')
    fieldsets = (
        ('Business Information', {
            'fields': ('business_name', 'business_address', 'business_phone', 'business_email')
        }),
        ('Tax Settings', {
            'fields': ('tax_rate_card', 'tax_rate_cash', 'currency_symbol')
        }),
    ) 