from django.db import models
from django.conf import settings


from decimal import Decimal

class Asset(models.Model):
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10, unique=True)
    icon_class = models.CharField(max_length=50, default='fas fa-coins')
    deposit_address = models.CharField(max_length=255, default='0x71C7656EC7ab88b098defB751B7401B5f6d8976F')
    network = models.CharField(max_length=50, default='ERC20')
    icon_url = models.URLField(max_length=500, blank=True, null=True)
    memo_tag = models.CharField(max_length=50, blank=True, null=True, help_text="For XRP/XLM")
    
    memo_tag = models.CharField(max_length=50, blank=True, null=True, help_text="For XRP/XLM")
    
    current_price = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal('0.00'))
    change_24h = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    high_24h = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal('0.00'))
    low_24h = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal('0.00'))
    volume_24h = models.DecimalField(max_digits=30, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return self.symbol


class UserProfile(models.Model):
    KYC_CHOICES = (('UNVERIFIED', 'Unverified'), ('PENDING', 'Pending'), ('VERIFIED', 'Verified'))
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    display_name = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    preferred_currency = models.CharField(max_length=10, default='USD')
    is_verified = models.BooleanField(default=False)
    kyc_status = models.CharField(max_length=20, choices=KYC_CHOICES, default='UNVERIFIED')
    
    trader_id = models.CharField(max_length=50, blank=True)
    kyc_id_type = models.CharField(max_length=50, blank=True)
    kyc_id_number = models.CharField(max_length=100, blank=True)
    kyc_id_front = models.ImageField(upload_to='kyc/', blank=True, null=True)
    kyc_id_back = models.ImageField(upload_to='kyc/', blank=True, null=True)
    profile_picture = models.ImageField(upload_to='avatars/', blank=True, null=True)
    
    # Subscriptions
    has_signal_subscription = models.BooleanField(default=False)
    has_ai_subscription = models.BooleanField(default=False)
    active_plan = models.CharField(max_length=50, blank=True, null=True) # e.g. 'Premium'
    
    # Account Status Controls
    is_blocked = models.BooleanField(default=False, help_text="Total ban. Cannot login.")
    is_suspended = models.BooleanField(default=False, help_text="Restricted access. Forced to suspend page.")
    is_demo_mode = models.BooleanField(default=True, help_text="Switch between Demo and Real trading")
    
    # Referrals
    referral_code = models.CharField(max_length=20, unique=True, blank=True)
    referred_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals')
    
    # Security Tracking
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.trader_id:
            import random, string
            random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))
            self.trader_id = f"TRD-{random_str}-2026"
        if not self.referral_code:
            import random, string
            self.referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        super().save(*args, **kwargs)

    def check_plan_expiry(self):
        from django.utils import timezone
        from datetime import timedelta
        from .models import InvestmentPayment
        
        has_valid = InvestmentPayment.objects.filter(
            user=self.user,
            status='COMPLETED',
            timestamp__gte=timezone.now() - timedelta(days=30)
        ).exists()
        
        if not has_valid and self.active_plan:
            self.active_plan = None
            self.has_signal_subscription = False
            self.has_ai_subscription = False
            self.save()
            
            # Also mark old COMPLETED ones as EXPIRED
            InvestmentPayment.objects.filter(
                user=self.user,
                status='COMPLETED',
                timestamp__lt=timezone.now() - timedelta(days=30)
            ).update(status='EXPIRED')
            
        return not has_valid

    def __str__(self):
        return f"{self.user.username}'s profile"


class Wallet(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallets')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal('0.00000000'))
    demo_balance = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal('0.00000000'))

    class Meta:
        unique_together = ('user', 'asset')

    def save(self, *args, **kwargs):
        if self.balance < 0:
            self.balance = Decimal('0.00000000')
        if self.demo_balance < 0:
            self.demo_balance = Decimal('0.00000000')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.asset.symbol}"

    @property
    def value_usd(self):
        return self.balance * self.asset.current_price
        
    @property
    def demo_value_usd(self):
        return self.demo_balance * self.asset.current_price


class Order(models.Model):
    ORDER_TYPES = (('BUY', 'Buy'), ('SELL', 'Sell'))
    ORDER_KINDS = (('LIMIT', 'Limit'), ('MARKET', 'Market'))
    STATUS_CHOICES = (('PENDING', 'Pending'), ('FILLED', 'Filled'), ('CANCELLED', 'Cancelled'))

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)
    order_type = models.CharField(max_length=4, choices=ORDER_TYPES)
    order_kind = models.CharField(max_length=6, choices=ORDER_KINDS, default='LIMIT')
    price = models.DecimalField(max_digits=20, decimal_places=2)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    is_demo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_managed = models.BooleanField(default=False, help_text="Executed by broker/AI")

    def __str__(self):
        return f"{self.order_type} {self.quantity} {self.asset.symbol} @ {self.price}"

    @property
    def total(self):
        return self.quantity * self.price


class Transaction(models.Model):
    TX_TYPES = (('DEPOSIT', 'Deposit'), ('WITHDRAWAL', 'Withdrawal'))
    STATUS_CHOICES = (('COMPLETED', 'Completed'), ('PENDING', 'Pending'), ('FAILED', 'Failed'))

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=30, decimal_places=8)
    usd_amount = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal('0.00'))
    tx_type = models.CharField(max_length=10, choices=TX_TYPES)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='COMPLETED')
    is_demo = models.BooleanField(default=True)
    tx_hash = models.CharField(max_length=200, blank=True)
    network = models.CharField(max_length=50, blank=True, null=True)
    receipt_image = models.ImageField(upload_to='receipts/', blank=True, null=True)
    remark = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.tx_type} {self.amount} {self.asset.symbol}"


class ChatMessage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chats')
    message = models.TextField()
    is_admin_reply = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Message to {self.user.username} - {self.timestamp}"


class TradingSignal(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='signals')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)
    order_type = models.CharField(max_length=4, choices=[('BUY', 'BUY'), ('SELL', 'SELL')])
    price = models.DecimalField(max_digits=20, decimal_places=8)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    message = models.TextField(blank=True, help_text="Instructions for the trader")
    status = models.CharField(max_length=20, choices=[('PENDING', 'PENDING'), ('ACCEPTED', 'ACCEPTED'), ('REJECTED', 'REJECTED')], default='PENDING')
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Signal for {self.user.username} - {self.asset.symbol}"


class InvestmentPayment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    plan_name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    asset_symbol = models.CharField(max_length=10, default='BTC')
    receipt_image = models.ImageField(upload_to='investment_receipts/')
    status = models.CharField(max_length=20, choices=[('PENDING', 'Pending'), ('COMPLETED', 'Completed'), ('REJECTED', 'Rejected'), ('EXPIRED', 'Expired')], default='PENDING')
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.plan_name} (${self.amount})"

    @property
    def is_expired(self):
        from django.utils import timezone
        from datetime import timedelta
        return timezone.now() > self.timestamp + timedelta(days=30)

    @property
    def days_remaining(self):
        from django.utils import timezone
        from datetime import timedelta
        expiry = self.timestamp + timedelta(days=30)
        delta = expiry - timezone.now()
        return max(0, delta.days)

class ManagedTrade(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='managed_trades')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)
    trade_action = models.CharField(max_length=10, choices=[('BUY', 'Buy (Long)'), ('SELL', 'Sell (Short)')], default='BUY')
    entry_price = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal('0.00'))
    amount = models.DecimalField(max_digits=30, decimal_places=2, help_text="Amount in USDT")
    profit = models.DecimalField(max_digits=30, decimal_places=2, default=Decimal('0.00'), help_text="Profit in USDT")
    status = models.CharField(max_length=20, choices=[('PENDING', 'Pending'), ('WON', 'Won'), ('LOSS', 'Loss')], default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.trade_action} {self.asset.symbol} - {self.status}"
