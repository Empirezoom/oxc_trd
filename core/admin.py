from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import Asset, UserProfile, Wallet, Order, Transaction, InvestmentPayment
from .email_utils import send_notification_email


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'name', 'current_price', 'change_24h', 'high_24h', 'low_24h', 'volume_24h')
    search_fields = ('symbol', 'name')
    list_editable = ('current_price', 'change_24h')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'display_name', 'is_verified', 'preferred_currency', 'created_at')
    list_filter = ('is_verified', 'preferred_currency')
    search_fields = ('user__username', 'display_name')


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'asset', 'balance', 'value_usd')
    list_filter = ('asset',)
    search_fields = ('user__username', 'asset__symbol')

    def value_usd(self, obj):
        return f"${obj.value_usd:,.2f}"
    value_usd.short_description = 'Value (USD)'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('user', 'asset', 'order_type', 'order_kind', 'quantity', 'price', 'total_display', 'status', 'created_at')
    list_filter = ('order_type', 'order_kind', 'status', 'asset')
    search_fields = ('user__username', 'asset__symbol')
    list_editable = ('status',)

    def total_display(self, obj):
        return f"${obj.total:,.2f}"
    total_display.short_description = 'Total'


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'asset', 'tx_type', 'amount', 'status', 'timestamp')
    list_filter = ('tx_type', 'status', 'asset')
    search_fields = ('user__username', 'asset__symbol', 'tx_hash')

@admin.register(InvestmentPayment)
class InvestmentPaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan_name', 'amount', 'status', 'timestamp')
    list_filter = ('status', 'plan_name')
    search_fields = ('user__username', 'plan_name')
    list_editable = ('status',)

    def save_model(self, request, obj, form, change):
        if change:
            old_status = InvestmentPayment.objects.get(pk=obj.pk).status
            if old_status != obj.status:
                if obj.status == 'COMPLETED':
                    send_notification_email(obj.user, "Investment Verified ✅", "payment_approved.html", {
                        'payment': obj
                    })
                elif obj.status == 'REJECTED':
                    send_notification_email(obj.user, "Investment Update ❌", "payment_rejected.html", {
                        'payment': obj
                    })
        super().save_model(request, obj, form, change)
