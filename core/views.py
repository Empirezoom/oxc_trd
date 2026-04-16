from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Sum, Q, Count, Max
from django.http import JsonResponse
from django.contrib.auth.decorators import user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from .models import Asset, Wallet, Order, Transaction, UserProfile, ChatMessage, TradingSignal, InvestmentPayment
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from datetime import timedelta
from django.views.decorators.csrf import csrf_exempt
import json
from .email_utils import send_notification_email

@staff_member_required(login_url='login')
def api_admin_delete_message(request, message_id):
    if request.method == 'POST':
        msg = get_object_or_404(ChatMessage, id=message_id)
        msg.delete()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'}, status=400)


# ─── Auth Views ────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('index')
    error = None
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            try:
                if user.profile.is_blocked:
                    return render(request, 'core/login.html', {'error': 'ACCESS DENIED: Your account has been permanently restricted for policy violations.'})
            except:
                pass
            login(request, user)
            
            # Update Security Tracking (Exclude Admins/Staff)
            if not user.is_staff and not user.is_superuser:
                x_f = request.META.get('HTTP_X_FORWARDED_FOR')
                ip = x_f.split(',')[0] if x_f else request.META.get('REMOTE_ADDR')
                user.profile.last_login_ip = ip
                user.profile.last_login_at = timezone.now()
                user.profile.save()

            # Email Notification
            send_notification_email(user, "New Login Detected", "login.html", {
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            })

            if user.is_superuser:
                return redirect('custom_admin_dashboard')
            return redirect('index')
        else:
            error = "Invalid username or password."
    return render(request, 'core/login.html', {'error': error})


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('index')
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')

        if not username or not email or not password:
            error = "All fields are required."
        elif password != password2:
            error = "Passwords do not match."
        elif User.objects.filter(username=username).exists():
            error = "Username already taken."
        elif User.objects.filter(email=email).exists():
            error = "Email already registered."
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            profile = UserProfile.objects.create(user=user)
            login(request, user)
            
            # Email Notification
            send_notification_email(user, "Welcome to OctalX", "signup.html", {
                'site_url': settings.SITE_URL
            })

            # Referral logic
            ref_code = request.GET.get('ref')
            if ref_code:
                try:
                    referrer_profile = UserProfile.objects.get(trader_id=ref_code)
                    profile.referred_by = referrer_profile.user
                    profile.save()
                    
                    # Credit $5 to referrer's BTC wallet
                    btc_asset = Asset.objects.get(symbol='BTC')
                    if btc_asset.current_price > 0:
                        btc_wallet, _ = Wallet.objects.get_or_create(user=referrer_profile.user, asset=btc_asset)
                        bonus_qty = Decimal('5.00') / btc_asset.current_price
                        btc_wallet.balance += bonus_qty
                        btc_wallet.save()
                        
                        Transaction.objects.create(
                            user=referrer_profile.user,
                            asset=btc_asset,
                            amount=bonus_qty,
                            usd_amount=Decimal('5.00'),
                            tx_type='DEPOSIT',
                            status='COMPLETED',
                            remark=f"Referral Bonus: {user.username}",
                            is_demo=False
                        )
                except:
                    pass
            
            return redirect('index')
    return render(request, 'core/signup.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('login')


# ─── Main Pages ────────────────────────────────────────────────────────────────

def index(request):
    if request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.is_suspended:
        return redirect('suspended')
    assets = Asset.objects.all()
    orders = []
    history = []
    positions = []
    is_demo_mode = True
    profile = None
    if request.user.is_authenticated:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        is_demo_mode = profile.is_demo_mode
        # Open Orders
        orders = Order.objects.filter(user=request.user, status='PENDING', is_demo=is_demo_mode).select_related('asset').order_by('-created_at')
        # Recently Filled/Cancelled History
        history = Order.objects.filter(user=request.user, is_demo=is_demo_mode).exclude(status='PENDING').select_related('asset').order_by('-updated_at')[:20]
        # Active Positions (Wallets with balance > 0, excluding USDT)
        positions = list(Wallet.objects.filter(user=request.user).exclude(asset__symbol='USDT').select_related('asset'))
        filtered_positions = []
        for w in positions:
            w.display_balance = w.demo_balance if is_demo_mode else w.balance
            w.display_value = w.demo_value_usd if is_demo_mode else w.value_usd
            if w.display_balance > 0:
                filtered_positions.append(w)
        positions = filtered_positions
        
        # DEMO MODE: Seed 10,000 USDT for new users to test trading
        usdt_asset, _ = Asset.objects.get_or_create(symbol='USDT', defaults={'name': 'Tether (USDT)', 'current_price': 1.00})
        usdt_wallet, created = Wallet.objects.get_or_create(user=request.user, asset=usdt_asset)
        if created:
            usdt_wallet.demo_balance = Decimal('10000.00')
            usdt_wallet.save()
            messages.info(request, "Welcome! We've credited your account with 10,000 Demo USDT so you can test trading.")

    # Handle order placement via POST
    if request.method == 'POST' and request.user.is_authenticated:
        return place_order(request)

    context = {
        'assets': assets,
        'orders': orders,
        'history': history,
        'positions': positions,
        'is_demo_mode': is_demo_mode,
    }
    return render(request, 'core/index.html', context)


def market(request):
    assets = Asset.objects.all().order_by('-volume_24h')
    context = {'assets': assets}
    return render(request, 'core/market.html', context)


def wallet_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if profile.is_suspended:
        return redirect('suspended')

    user_wallets = list(Wallet.objects.filter(user=request.user).select_related('asset'))
    is_demo_mode = profile.is_demo_mode
    total_balance = 0
    for w in user_wallets:
        w.display_balance = w.demo_balance if is_demo_mode else w.balance
        w.display_value = w.demo_value_usd if is_demo_mode else w.value_usd
        total_balance += w.display_value

    # Handle deposit/withdrawal
    if request.method == 'POST':
        tx_type = request.POST.get('tx_type')
        asset_symbol = request.POST.get('asset_symbol')
        try:
            amount = Decimal(request.POST.get('amount', '0'))
            asset = Asset.objects.get(symbol=asset_symbol)
            wallet_obj, _ = Wallet.objects.get_or_create(user=request.user, asset=asset)

            if tx_type == 'DEPOSIT':
                receipt = request.FILES.get('receipt_image')
                # Amount from form is USD
                usd_amount = amount 
                # Calculate crypto amount: USD / Current Price
                if asset.current_price > 0:
                    asset_amount = usd_amount / asset.current_price
                else:
                    asset_amount = Decimal('0')

                status = 'COMPLETED' if is_demo_mode else 'PENDING'
                
                Transaction.objects.create(
                    user=request.user, 
                    asset=asset, 
                    amount=asset_amount, # Crypto amount
                    usd_amount=usd_amount, # USD Reference
                    tx_type='DEPOSIT', 
                    status=status, 
                    receipt_image=receipt,
                    is_demo=is_demo_mode
                )
                
                if is_demo_mode:
                    wallet_obj.demo_balance += asset_amount
                    wallet_obj.save()
                    messages.success(request, f"Demo deposit of ${usd_amount} ({asset_amount:.8f} {asset_symbol}) credited instantly.")
                else:
                    messages.success(request, f"Deposit request for ${usd_amount} ({asset_amount:.8f} {asset_symbol}) submitted. Waiting for admin approval.")
            elif tx_type == 'WITHDRAWAL':
                if is_demo_mode:
                    messages.error(request, "Withdrawals are only available for Real accounts.")
                    return redirect('wallet')
                    
                usd_val = amount * asset.current_price
                dest_addr = request.POST.get('dest_address', '')
                network = request.POST.get('network', 'N/A')
                
                if usd_val < 10000:
                    messages.error(request, f"Minimum withdrawal amount is $10,000. Current request: ${usd_val:,.2f}")
                else:
                    balance_field = wallet_obj.balance
                    if balance_field >= amount:
                        # In a real system, we might hold the funds in 'Pending'
                        wallet_obj.balance -= amount
                        wallet_obj.save()
                        Transaction.objects.create(
                            user=request.user, 
                            asset=asset, 
                            amount=amount, 
                            usd_amount=usd_val,
                            tx_type='WITHDRAWAL', 
                            status='PENDING', # Admin must confirm
                            tx_hash=dest_addr, # Using tx_hash to store destination address
                            network=network,
                            is_demo=False
                        )
                        messages.success(request, f"Withdrawal request for {amount} {asset_symbol} (${usd_val:,.2f}) submitted.")
                    else:
                        messages.error(request, "Insufficient balance.")
        except (InvalidOperation, Asset.DoesNotExist):
            messages.error(request, "Invalid transaction.")
        return redirect('wallet')

    recent_transactions = Transaction.objects.filter(user=request.user, is_demo=is_demo_mode).select_related('asset').order_by('-timestamp')[:10]
    context = {
        'wallets': user_wallets,
        'total_balance': total_balance,
        'transactions': recent_transactions,
        'assets': Asset.objects.all(),
        'is_demo_mode': is_demo_mode,
    }
    return render(request, 'core/wallet.html', context)


def order_history_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    is_demo_mode = profile.is_demo_mode
    orders = Order.objects.filter(user=request.user, is_demo=is_demo_mode).select_related('asset').order_by('-created_at')
    
    filled_count = orders.filter(status='FILLED').count()
    pending_count = orders.filter(status='PENDING').count()
    cancelled_count = orders.filter(status='CANCELLED').count()
    
    context = {
        'orders': orders,
        'filled_count': filled_count,
        'pending_count': pending_count,
        'cancelled_count': cancelled_count,
        'is_demo_mode': is_demo_mode,
    }
    return render(request, 'core/order_history.html', context)

def transaction_history_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    is_demo_mode = profile.is_demo_mode
    transactions = Transaction.objects.filter(user=request.user, is_demo=is_demo_mode).select_related('asset').order_by('-timestamp')
    return render(request, 'core/transaction_history.html', {'transactions': transactions, 'is_demo_mode': is_demo_mode})


def profile_view(request):
    if not request.user.is_authenticated:
        return redirect('login')

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    pw_form = PasswordChangeForm(request.user)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_profile':
            profile.display_name = request.POST.get('display_name', '')
            profile.bio = request.POST.get('bio', '')
            profile.phone = request.POST.get('phone', '')
            profile.preferred_currency = request.POST.get('preferred_currency', 'USD')
            
            if 'profile_pic' in request.FILES:
                profile.profile_picture = request.FILES['profile_pic']
            
            profile.save()
            messages.success(request, "Profile updated successfully.")
            return redirect('profile')
            
        elif action == 'submit_kyc':
            profile.kyc_id_type = request.POST.get('id_type', '')
            profile.kyc_id_number = request.POST.get('id_number', '')
            if 'id_front' in request.FILES: profile.kyc_id_front = request.FILES['id_front']
            if 'id_back' in request.FILES: profile.kyc_id_back = request.FILES['id_back']
            profile.kyc_status = 'PENDING'
            profile.save()
            messages.success(request, "Verification documents submitted!")
            return redirect('profile')
            
        elif 'change_password' in request.POST:
            pw_form = PasswordChangeForm(request.user, request.POST)
            if pw_form.is_valid():
                user = pw_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Password changed successfully.")
                return redirect('profile')
            else:
                messages.error(request, "Password change failed.")

    context = {
        'profile': profile,
        'pw_form': pw_form,
    }
    return render(request, 'core/profile.html', context)


@user_passes_test(lambda u: u.is_authenticated)
def api_upload_avatar(request):
    if request.method == 'POST' and request.FILES.get('profile_pic'):
        profile = get_object_or_404(UserProfile, user=request.user)
        # Delete old file if it exists
        if profile.profile_picture:
            import os
            if os.path.exists(profile.profile_picture.path):
                os.remove(profile.profile_picture.path)
        
        profile.profile_picture = request.FILES['profile_pic']
        profile.save()
        return JsonResponse({'status': 'ok', 'url': profile.profile_picture.url})
    return JsonResponse({'status': 'error'}, status=400)


# ─── Order Logic ───────────────────────────────────────────────────────────────

def place_order(request):
    """Processes order placement with balance validation and settlement logic."""
    try:
        symbol = request.POST.get('symbol', 'BTC')
        order_type = request.POST.get('order_type', 'BUY')
        order_kind = request.POST.get('order_kind', 'LIMIT')
        quantity = Decimal(request.POST.get('quantity', '0'))
        
        asset = get_object_or_404(Asset, symbol=symbol)
        usdt_asset = get_object_or_404(Asset, symbol='USDT')
        
        # In Market mode, use current asset price
        if order_kind == 'MARKET':
            price = asset.current_price
        else:
            price = Decimal(request.POST.get('price', '0'))

        if quantity <= 0 or price <= 0:
            messages.error(request, "Invalid quantity or price.")
            return redirect('index')

        total_cost = quantity * price
        
        # Get/Create Wallets
        usdt_wallet, _ = Wallet.objects.get_or_create(user=request.user, asset=usdt_asset)
        asset_wallet, _ = Wallet.objects.get_or_create(user=request.user, asset=asset)

        status = 'PENDING'
        
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        is_demo_mode = profile.is_demo_mode

        if order_type == 'BUY':
            balance_field = usdt_wallet.demo_balance if is_demo_mode else usdt_wallet.balance
            if balance_field < total_cost:
                messages.error(request, f"Insufficient USDT. Need ${total_cost:,.2f}, have ${balance_field:,.2f}")
                return redirect('index')
            
            if order_kind == 'MARKET':
                if is_demo_mode:
                    usdt_wallet.demo_balance -= total_cost
                    asset_wallet.demo_balance += quantity
                else:
                    usdt_wallet.balance -= total_cost
                    asset_wallet.balance += quantity
                # Safety Clamp
                usdt_wallet.balance = max(Decimal('0'), usdt_wallet.balance)
                usdt_wallet.demo_balance = max(Decimal('0'), usdt_wallet.demo_balance)
                status = 'FILLED'
            else:
                if is_demo_mode:
                    usdt_wallet.demo_balance -= total_cost
                else:
                    usdt_wallet.balance -= total_cost
            
            usdt_wallet.save()
            asset_wallet.save()

        else: # SELL
            balance_field = asset_wallet.demo_balance if is_demo_mode else asset_wallet.balance
            if balance_field < quantity:
                messages.error(request, f"Insufficient {symbol}. Need {quantity}, have {balance_field}")
                return redirect('index')
                
            if order_kind == 'MARKET':
                if is_demo_mode:
                    asset_wallet.demo_balance -= quantity
                    usdt_wallet.demo_balance += total_cost
                else:
                    asset_wallet.balance -= quantity
                    usdt_wallet.balance += total_cost
                status = 'FILLED'
            else:
                if is_demo_mode:
                    asset_wallet.demo_balance -= quantity
                else:
                    asset_wallet.balance -= quantity
                # Safety Clamp
                asset_wallet.balance = max(Decimal('0'), asset_wallet.balance)
                asset_wallet.demo_balance = max(Decimal('0'), asset_wallet.demo_balance)
            
            asset_wallet.save()
            usdt_wallet.save()

        Order.objects.create(
            user=request.user,
            asset=asset,
            order_type=order_type,
            order_kind=order_kind,
            quantity=quantity,
            price=price,
            status=status,
            is_demo=is_demo_mode,
        )
        msg_verb = "executed" if status == 'FILLED' else "placed"
        messages.success(request, f"{order_type} {order_kind} order for {quantity} {symbol} {msg_verb} successfully!")
        
    except (InvalidOperation, Asset.DoesNotExist) as e:
        messages.error(request, f"Order failed: {str(e)}")

    return redirect('index')


def cancel_order(request, order_id):
    """Cancels a pending order and refunds the 'locked' balance to the user's wallet."""
    if not request.user.is_authenticated:
        return redirect('login')
        
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if order.status == 'PENDING':
        # Refund locked funds/assets
        if order.order_type == 'BUY':
            # Refund USDT
            usdt_asset = Asset.objects.get(symbol='USDT')
            wallet, _ = Wallet.objects.get_or_create(user=request.user, asset=usdt_asset)
            if order.is_demo:
                wallet.demo_balance += (order.quantity * order.price)
            else:
                wallet.balance += (order.quantity * order.price)
            wallet.save()
        else:
            # Refund the Asset
            wallet, _ = Wallet.objects.get_or_create(user=request.user, asset=order.asset)
            if order.is_demo:
                wallet.demo_balance += order.quantity
            else:
                wallet.balance += order.quantity
            wallet.save()
            
        order.status = 'CANCELLED'
        order.save()
        messages.success(request, f"Order #{order.id} cancelled. Locked funds have been returned to your wallet.")
    else:
        messages.error(request, "Only pending orders can be cancelled.")
        
    return redirect('index')


# ─── API Endpoint ──────────────────────────────────────────────────────────────

def api_assets(request):
    """Returns asset data as JSON for the chart pair switcher."""
    assets = Asset.objects.all().values('symbol', 'name', 'current_price', 'change_24h', 'high_24h', 'low_24h', 'volume_24h')
    return JsonResponse({'assets': list(assets)})

@user_passes_test(lambda u: u.is_authenticated)
def toggle_demo_mode(request):
    if request.method == 'POST':
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.is_demo_mode = not profile.is_demo_mode
        profile.save()
        messages.success(request, f"Switched to {'Demo' if profile.is_demo_mode else 'Real'} Trading mode.")
        # Redirect back to the previous page, or index if not available
        return redirect(request.META.get('HTTP_REFERER', 'index'))
    return JsonResponse({'status': 'error'}, status=400)


# ─── Minor Pages ───────────────────────────────────────────────────────────────

def terms_view(request):
    return render(request, 'core/terms.html')

def privacy_view(request):
    return render(request, 'core/privacy.html')

def error_404(request, exception=None):
    return render(request, '404.html', status=404)

def forgot_password_view(request):
    if request.method == 'POST':
        messages.success(request, "If the email is registered, a reset link will be sent.")
        return redirect('login')
    return render(request, 'core/forgot_password.html')

def suspended_page(request):
    return render(request, 'core/suspended.html')

def user_chat_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    # Handle incoming messages from user
    if request.method == 'POST':
        msg_text = request.POST.get('message')
        if msg_text:
            ChatMessage.objects.create(
                user=request.user,
                message=msg_text,
                is_admin_reply=False
            )
            return redirect('user_chat')

    messages = ChatMessage.objects.filter(user=request.user).exclude(message__contains='SIGNAL:').order_by('timestamp')
    
    # Fetch signals
    signals = TradingSignal.objects.filter(user=request.user)

    # Combine and sort into a single timeline
    timeline = sorted(
        list(messages) + list(signals),
        key=lambda x: x.timestamp
    )
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    return render(request, 'core/user_chat.html', {
        'timeline': timeline,
        'profile': profile
    })

@staff_member_required(login_url='login')
def admin_ai_trading(request):
    from django.db.models import Q
    managed_users = UserProfile.objects.filter(
        Q(active_plan__in=['Premium', 'Enterprise', 'Platinum', 'Ultimate']) | Q(has_ai_subscription=True)
    ).select_related('user').distinct()
    
    assets = Asset.objects.all()
    
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        asset_id = request.POST.get('asset_id')
        status = request.POST.get('status')
        trade_action = request.POST.get('trade_action', 'BUY')
        entry_price = Decimal(request.POST.get('entry_price', '0'))
        amount = Decimal(request.POST.get('amount', '0'))
        profit = Decimal(request.POST.get('profit', '0'))
        
        target_user = get_object_or_404(User, id=user_id)
        asset = get_object_or_404(Asset, id=asset_id)
        
        # Check if user has enough of the specific Asset to stake the USD amount
        # (e.g. if trading BTC, we check if they have enough BTC value to cover the $ stake)
        asset_wallet, _ = Wallet.objects.get_or_create(user=target_user, asset=asset)
        
        # Calculate quantity to lock from the specific asset wallet
        deduct_qty = Decimal('0')
        if asset.current_price > 0:
            deduct_qty = amount / asset.current_price
            
        print(f"MANAGED TRADE CHECK: User {target_user.username} has {asset_wallet.balance} {asset.symbol}. Required deduct: {deduct_qty}")

        if not target_user.profile.has_ai_subscription:
            messages.error(request, f"INACTIVE: {target_user.username} does not have an active AI/Elite subscription.")
            return redirect('admin_ai_trading')

        if asset_wallet.balance < deduct_qty:
            messages.error(request, f"INSUFFICIENT {asset.symbol}: {target_user.username} only has {asset_wallet.balance} {asset.symbol} (Value: ${asset_wallet.value_usd:,.2f}). This trade requires ${amount:,.2f} stake.")
            return redirect('admin_ai_trading')
            
        asset_wallet.balance -= deduct_qty
        asset_wallet.save()
        
        # Profit is credited to USDT wallet as per standard practice
        usdt_asset, _ = Asset.objects.get_or_create(symbol='USDT', defaults={'name': 'Tether (USDT)', 'current_price': 1.00})
        usdt_wallet, _ = Wallet.objects.get_or_create(user=target_user, asset=usdt_asset)
        
        if status == 'WON':
            # Return original stake to BTC and profit to USDT? 
            # Actually let's return everything to the original asset wallet for simplicity in this managed context
            profit_qty = profit / asset.current_price if asset.current_price > 0 else Decimal('0')
            asset_wallet.balance += (deduct_qty + profit_qty)
            asset_wallet.save()
            
            Transaction.objects.create(
                user=target_user, asset=asset, amount=deduct_qty+profit_qty, 
                usd_amount=amount+profit,
                tx_type='DEPOSIT', status='COMPLETED', 
                remark=f"Managed Trade WIN ({asset.symbol})", is_demo=False
            )
        
        from .models import ManagedTrade
        ManagedTrade.objects.create(
            user=target_user, asset=asset, trade_action=trade_action, entry_price=entry_price, amount=amount, profit=profit, status=status
        )
        
        messages.success(request, f"Investment Trade executed for {target_user.username}")
        
        # Email Notification for AI Trade
        send_notification_email(target_user, "Elite Trade Execution Notice", "ai_trade.html", {
            'trade': {
                'asset': asset,
                'status': status,
                'amount': amount,
                'profit': profit
            }
        })
        
        return redirect('admin_ai_trading')

    return render(request, 'core/custom_admin/ai_trading.html', {
        'managed_users': managed_users,
        'assets': assets
    })

@user_passes_test(lambda u: u.is_active and u.is_superuser, login_url='login')
def admin_managed_history(request):
    from .models import ManagedTrade
    managed_trades = ManagedTrade.objects.select_related('user', 'asset').order_by('-created_at')
    return render(request, 'core/custom_admin/managed_history.html', {'trades': managed_trades})

@staff_member_required(login_url='login')
def admin_manage_trade_action(request, trade_id, action):
    from .models import ManagedTrade
    trade = get_object_or_404(ManagedTrade, id=trade_id)
    if trade.status == 'PENDING':
        if action in ['WON', 'LOSS']:
            trade.status = action
            trade.save()
            
            if action == 'WON':
                # Return original stake + profit to the asset wallet
                wallet, _ = Wallet.objects.get_or_create(user=trade.user, asset=trade.asset)
                profit_qty = trade.profit / trade.asset.current_price if trade.asset.current_price > 0 else Decimal('0')
                stake_qty = trade.amount / trade.asset.current_price if trade.asset.current_price > 0 else Decimal('0')
                
                wallet.balance += (stake_qty + profit_qty)
                wallet.save()
                
                Transaction.objects.create(
                    user=trade.user, asset=trade.asset, amount=stake_qty+profit_qty,
                    usd_amount=trade.amount+trade.profit,
                    tx_type='DEPOSIT', status='COMPLETED', 
                    remark=f"Managed Trade WIN ({trade.asset.symbol})", is_demo=False
                )
            messages.success(request, f"Trade updated to {action}.")
    return redirect('admin_managed_history')

@user_passes_test(lambda u: u.is_authenticated)
def user_ai_trades_view(request):
    from .models import ManagedTrade
    trades = ManagedTrade.objects.filter(user=request.user).order_by('-created_at')
    
    # Calculate real-time Total USD balance across all assets
    user_wallets = request.user.wallets.select_related('asset').all()
    total_usd = sum(w.balance * w.asset.current_price for w in user_wallets)
    
    return render(request, 'core/user_ai_trades.html', {'trades': trades, 'total_usd': total_usd})


# ─── Custom Admin Console ──────────────────────────────────────────────────────

@user_passes_test(lambda u: u.is_active and u.is_superuser, login_url='login')
def custom_admin_dashboard(request):
    users_count = User.objects.filter(is_superuser=False).count()
    assets_count = Asset.objects.count()
    active_orders = Order.objects.filter(status='PENDING', is_demo=False).count()
    total_tx_vol = sum(tx.amount for tx in Transaction.objects.filter(tx_type='DEPOSIT', status='COMPLETED', is_demo=False))
    
    recent_users = User.objects.filter(is_superuser=False).order_by('-date_joined')[:5]
    recent_transactions = Transaction.objects.filter(is_demo=False).order_by('-timestamp')[:5]
    
    context = {
        'users_count': users_count,
        'assets_count': assets_count,
        'active_orders': active_orders,
        'total_tx_vol': total_tx_vol,
        'recent_users': recent_users,
        'recent_transactions': recent_transactions,
    }
    return render(request, 'core/custom_admin/dashboard.html', context)

@user_passes_test(lambda u: u.is_active and u.is_superuser, login_url='login')
def admin_security_logs(request):
    q = request.GET.get('q', '')
    profiles = UserProfile.objects.select_related('user').filter(
        last_login_at__isnull=False,
        user__is_staff=False,
        user__is_superuser=False
    )
    
    if q:
        profiles = profiles.filter(
            Q(user__username__icontains=q) |
            Q(user__email__icontains=q) |
            Q(trader_id__icontains=q)
        )
        
    profiles = profiles.order_by('-last_login_at')
    return render(request, 'core/custom_admin/security_logs.html', {'profiles': profiles, 'q': q})

@user_passes_test(lambda u: u.is_active and u.is_superuser, login_url='login')
def custom_admin_users(request):
    users = UserProfile.objects.select_related('user').all()
    return render(request, 'core/custom_admin/users.html', {'users': users})

@user_passes_test(lambda u: u.is_active and u.is_superuser, login_url='login')
def custom_admin_assets(request):
    assets = Asset.objects.all()
    return render(request, 'core/custom_admin/assets.html', {'assets': assets})

@user_passes_test(lambda u: u.is_active and u.is_superuser, login_url='login')
def custom_admin_orders(request):
    orders = Order.objects.filter(is_demo=False).select_related('user', 'asset').order_by('-created_at')
    return render(request, 'core/custom_admin/orders.html', {'orders': orders})

@user_passes_test(lambda u: u.is_active and u.is_superuser, login_url='login')
def admin_deposits(request):
    transactions = Transaction.objects.filter(tx_type='DEPOSIT', is_demo=False).select_related('user', 'asset').order_by('-timestamp')
    return render(request, 'core/custom_admin/deposits.html', {'transactions': transactions})

@user_passes_test(lambda u: u.is_active and u.is_superuser, login_url='login')
def admin_withdrawals(request):
    transactions = Transaction.objects.filter(tx_type='WITHDRAWAL', is_demo=False).select_related('user', 'asset').order_by('-timestamp')
    return render(request, 'core/custom_admin/withdrawals.html', {'transactions': transactions})

@user_passes_test(lambda u: u.is_active and u.is_superuser, login_url='login')
def custom_admin_investments(request):
    investments = InvestmentPayment.objects.select_related('user').order_by('-timestamp')
    return render(request, 'core/custom_admin/investments.html', {'investments': investments})

@staff_member_required(login_url='login')
def custom_admin_user_detail(request, user_id):
    profile = get_object_or_404(UserProfile, user__id=user_id)
    wallets = Wallet.objects.filter(user=profile.user).select_related('asset')
    transactions = Transaction.objects.filter(user=profile.user, is_demo=False).select_related('asset').order_by('-timestamp')
    orders = Order.objects.filter(user=profile.user, is_demo=False).select_related('asset').order_by('-created_at')
    investments = InvestmentPayment.objects.filter(user=profile.user).order_by('-timestamp')
    
    return render(request, 'core/custom_admin/user_detail.html', {
        'profile': profile,
        'wallets': wallets,
        'transactions': transactions,
        'orders': orders,
        'investments': investments
    })

@staff_member_required(login_url='login')
@user_passes_test(lambda u: u.is_superuser)
def admin_manage_addresses(request):
    assets = Asset.objects.all()
    if request.method == 'POST':
        for asset in assets:
            new_addr = request.POST.get(f'addr_{asset.id}')
            new_memo = request.POST.get(f'memo_{asset.id}')
            if new_addr:
                asset.deposit_address = new_addr
                asset.memo_tag = new_memo
                asset.save()
        messages.success(request, "Wallet addresses updated successfully.")
        return redirect('admin_manage_addresses')
    
    return render(request, 'core/custom_admin/manage_addresses.html', {'assets': assets})

def admin_approve_tx(request, tx_id):
    tx = get_object_or_404(Transaction, id=tx_id)
    if tx.status == 'PENDING':
        tx.status = 'COMPLETED'
        tx.save()
        
        if tx.tx_type == 'DEPOSIT':
            wallet, _ = Wallet.objects.get_or_create(user=tx.user, asset=tx.asset)
            if tx.is_demo:
                wallet.demo_balance += tx.amount
            else:
                wallet.balance += tx.amount
            wallet.save()
            messages.success(request, f"Deposit of {tx.amount} {tx.asset.symbol} approved for {tx.user.username} ({'DEMO' if tx.is_demo else 'REAL'}).")
            return redirect('admin_deposits')
        else:
            messages.success(request, f"Withdrawal of {tx.amount} {tx.asset.symbol} approved for {tx.user.username} ({'DEMO' if tx.is_demo else 'REAL'}).")
            return redirect('admin_withdrawals')
            
    return redirect('admin_deposits')

@staff_member_required(login_url='login')
def admin_reject_tx(request, tx_id):
    tx = get_object_or_404(Transaction, id=tx_id)
    if tx.status == 'PENDING':
        # Refund withdrawal amount to wallet
        if tx.tx_type == 'WITHDRAWAL':
            wallet, _ = Wallet.objects.get_or_create(user=tx.user, asset=tx.asset)
            if tx.is_demo:
                wallet.demo_balance += tx.amount
            else:
                wallet.balance += tx.amount
            wallet.save()
            
        tx.status = 'FAILED'
        tx.save()
        messages.error(request, f"Transaction #{tx.id} rejected.")
    
    if tx.tx_type == 'DEPOSIT':
        return redirect('admin_deposits')
    return redirect('admin_withdrawals')

@staff_member_required(login_url='login')
def admin_verify_user(request, user_id):
    profile = get_object_or_404(UserProfile, user__id=user_id)
    if profile.kyc_status == 'PENDING':
        profile.kyc_status = 'VERIFIED'
        profile.is_verified = True
        profile.save()
        messages.success(request, f"User {profile.user.username} has been verified.")
    return redirect('custom_admin_users')

@staff_member_required(login_url='login')
def admin_reject_kyc(request, user_id):
    profile = get_object_or_404(UserProfile, user__id=user_id)
    if profile.kyc_status == 'PENDING':
        profile.kyc_status = 'UNVERIFIED'
        profile.is_verified = False
        profile.save()
        messages.warning(request, f"User {profile.user.username}'s KYC has been rejected.")
    return redirect('custom_admin_users')


# ─── Chat Views ───────────────────────────────────────────────────────────────

@user_passes_test(lambda u: u.is_authenticated)
def api_get_messages(request):
    msgs = ChatMessage.objects.filter(user=request.user).order_by('timestamp')
    data = []
    
    # Fetch all signals for this user
    recent_signals = TradingSignal.objects.filter(user=request.user).order_by('timestamp')
    
    for m in msgs:
        # Don't return the raw system message for signals, we'll render the real signal objects instead
        if 'SIGNAL:' in m.message:
            continue
            
        data.append({
            'type': 'message',
            'id': m.id,
            'message': m.message,
            'is_admin': m.is_admin_reply,
            'is_read': m.is_read,
            'time': m.timestamp.strftime('%H:%M'),
            'timestamp': m.timestamp.isoformat(),
        })
        
    for sig in recent_signals:
        # Calculate remaining time in seconds
        time_diff = (timezone.now() - sig.timestamp).total_seconds()
        remaining = max(0, int(60 - time_diff))
        
        # Format a display message if none exists
        display_msg = sig.message
        if not display_msg:
            display_msg = f"SIGNAL: {sig.order_type} {sig.asset.symbol} @ ${sig.price:,.2f}"

        # Smart expiry: If time is up but still pending, show as EXPIRED to the user
        current_status = sig.status
        if current_status == 'PENDING' and remaining <= 0:
            current_status = 'EXPIRED'

        data.append({
            'type': 'signal',
            'id': sig.id,
            'signal_id': sig.id,
            'signal_status': current_status,
            'is_admin': True,
            'order_type': sig.order_type,
            'price': float(sig.price),
            'quantity': float(sig.quantity),
            'symbol': getattr(sig.asset, 'symbol', 'UNKNOWN'),
            'message': display_msg,
            'remaining_seconds': remaining,
            'timestamp': sig.timestamp.isoformat(),
        })
        
    # Sort data by timestamp
    data = sorted(data, key=lambda x: x['timestamp'])
    
    return JsonResponse({'messages': data})

@user_passes_test(lambda u: u.is_authenticated)
def api_mark_as_read(request):
    if request.method == 'POST':
        ChatMessage.objects.filter(user=request.user, is_admin_reply=True, is_read=False).update(is_read=True)
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'}, status=400)

@user_passes_test(lambda u: u.is_active and u.is_superuser, login_url='login')
def api_admin_get_messages(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    # Mark user messages as read when admin polls
    ChatMessage.objects.filter(user=target_user, is_admin_reply=False, is_read=False).update(is_read=True)
    
    msgs = ChatMessage.objects.filter(user=target_user).order_by('timestamp')
    data = [{
        'id': m.id,
        'message': m.message,
        'is_admin': m.is_admin_reply,
        'is_read': m.is_read,
        'time': m.timestamp.strftime('%H:%M'),
    } for m in msgs]
    return JsonResponse({'messages': data})

@user_passes_test(lambda u: u.is_active and u.is_superuser, login_url='login')
def api_admin_send_message(request, user_id):
    if request.method == 'POST':
        target_user = get_object_or_404(User, id=user_id)
        data = json.loads(request.body)
        msg_text = data.get('message', '')
        if msg_text:
            ChatMessage.objects.create(user=target_user, message=msg_text, is_admin_reply=True)
            return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'}, status=400)

@user_passes_test(lambda u: u.is_authenticated)
def api_send_message(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        msg_text = data.get('message', '')
        if msg_text:
            ChatMessage.objects.create(user=request.user, message=msg_text)
            return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'}, status=400)

@user_passes_test(lambda u: u.is_active and u.is_superuser, login_url='login')
def admin_chat_list(request):
    from django.db.models import Max
    # Get users who have messages, ordered by newest message
    users_with_messages = User.objects.filter(chats__isnull=False).annotate(last_msg=Max('chats__timestamp')).order_by('-last_msg').distinct()
    return render(request, 'core/custom_admin/chat_list.html', {'users': users_with_messages})

@staff_member_required(login_url='login')
def api_admin_chat_list(request):
    from django.db.models import Max
    users = User.objects.filter(chats__isnull=False).annotate(
        last_msg=Max('chats__timestamp'),
        unread_count=Count('chats', filter=Q(chats__is_admin_reply=False, chats__is_read=False))
    ).order_by('-last_msg').distinct()
    
    data = []
    for u in users:
        data.append({
            'id': u.id,
            'username': u.username,
            'display_name': getattr(u, 'userprofile', u).display_name if hasattr(u, 'userprofile') else u.username,
            'last_msg_time': u.last_msg.strftime('%M %d, %H:%M') if u.last_msg else '',
            'unread_count': u.unread_count
        })
    return JsonResponse({'users': data})

@user_passes_test(lambda u: u.is_active and u.is_superuser, login_url='login')
def admin_chat_detail(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    
    # Mark user messages as read when admin opens the page
    ChatMessage.objects.filter(user=target_user, is_admin_reply=False, is_read=False).update(is_read=True)
    
    messages_list = ChatMessage.objects.filter(user=target_user).order_by('timestamp')
    
    if request.method == 'POST':
        msg_text = request.POST.get('message')
        if msg_text:
            ChatMessage.objects.create(user=target_user, message=msg_text, is_admin_reply=True)
            return redirect('admin_chat_detail', user_id=user_id)
            
    return render(request, 'core/custom_admin/chat_detail.html', {
        'target_user': target_user,
        'chat_messages': messages_list,
        'assets': Asset.objects.all()
    })


# ─── Empire Elite Investment Views ───────────────────────────────────────────

@staff_member_required(login_url='login')
def admin_send_signal(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    assets = Asset.objects.all()
    
    if request.method == 'POST':
        if not target_user.profile.has_signal_subscription:
            messages.error(request, f"BLOCK: User {target_user.username} signal access has expired or is inactive.")
            return redirect('admin_chat_detail', user_id=user_id)
            
        asset_id = request.POST.get('asset_id')
        order_type = request.POST.get('order_type')
        price = request.POST.get('price')
        qty = request.POST.get('quantity')
        
        asset = get_object_or_404(Asset, id=asset_id)
        
        # Create signal
        sig = TradingSignal.objects.create(
            user=target_user,
            asset=asset,
            order_type=order_type,
            price=price,
            quantity=qty,
            status='PENDING'
        )
        
        # Also notify user via ChatMessage
        ChatMessage.objects.create(
            user=target_user,
            message=f"SIGNAL: {order_type} {asset.symbol} at ${price}. Check your terminal to accept/reject.",
            is_admin_reply=True
        )
        
        messages.success(request, f"Signal sent to {target_user.username}")
        return redirect('admin_chat_detail', user_id=user_id)
        
    return redirect('admin_chat_detail', user_id=user_id)

@user_passes_test(lambda u: u.is_authenticated)
def api_respond_signal(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        sig_id = data.get('signal_id')
        action = data.get('action') # ACCEPTED or REJECTED
        
        sig = get_object_or_404(TradingSignal, id=sig_id, user=request.user, status='PENDING')
        sig.status = action
        sig.save()
        
        if action == 'ACCEPTED':
            # Create a trade in history
            asset_wallet, _ = Wallet.objects.get_or_create(user=request.user, asset=sig.asset)
            usdt_asset, _ = Asset.objects.get_or_create(symbol='USDT', defaults={'name': 'Tether (USDT)', 'current_price': 1.00})
            usdt_wallet, _ = Wallet.objects.get_or_create(user=request.user, asset=usdt_asset)
            
            # Simple simulation: we just record it as FILLED
            total = sig.price * sig.quantity
            Order.objects.create(
                user=request.user,
                asset=sig.asset,
                order_type=sig.order_type,
                order_kind='MARKET', 
                price=sig.price,
                quantity=sig.quantity,
                status='FILLED',
                is_managed=True,
                is_demo=False
            )
            
            # Update history balance (Real)
            if sig.order_type == 'BUY':
                usdt_wallet.balance -= total
                asset_wallet.balance += sig.quantity
            else:
                usdt_wallet.balance += total
                asset_wallet.balance -= sig.quantity
            usdt_wallet.save()
            asset_wallet.save()
            
            return JsonResponse({'status': 'ok', 'msg': f'Signal accepted and {sig.order_type} executed.'})
        
        return JsonResponse({'status': 'ok', 'msg': 'Signal rejected.'})
    return JsonResponse({'status': 'error'}, status=400)

@user_passes_test(lambda u: u.is_authenticated)
def investment_plans_view(request):
    return render(request, 'core/investment_plans.html')

@user_passes_test(lambda u: u.is_authenticated)
def investment_tiers_view(request):
    return render(request, 'core/investment_tier_selection.html')

@user_passes_test(lambda u: u.is_authenticated)
def investment_checkout_view(request):
    plan = request.GET.get('plan', 'Premium')
    amount = request.GET.get('amount', '1000')
    assets = Asset.objects.all()
    
    if request.method == 'POST':
        plan_name = request.POST.get('plan_name')
        amount_paid = request.POST.get('amount')
        asset_symbol = request.POST.get('asset_symbol')
        receipt = request.FILES.get('receipt_image')
        
        if receipt:
            InvestmentPayment.objects.create(
                user=request.user,
                plan_name=plan_name,
                amount=amount_paid,
                asset_symbol=asset_symbol,
                receipt_image=receipt,
                status='PENDING'
            )
            messages.success(request, f"Your payment for {plan_name} plan has been submitted for verification.")
            return redirect('my_investments')
            
    return render(request, 'core/investment_checkout.html', {
        'plan': plan,
        'amount': amount,
        'assets': assets
    })

@user_passes_test(lambda u: u.is_authenticated)
def my_investments_view(request):
    payments = InvestmentPayment.objects.filter(user=request.user).order_by('-timestamp')
    profile = request.user.profile
    
    # Referral link using Trader ID
    domain = request.get_host()
    ref_link = f"http://{domain}/signup/?ref={profile.trader_id}"
    
    return render(request, 'core/my_investments.html', {
        'payments': payments,
        'profile': profile,
        'ref_link': ref_link
    })

@staff_member_required(login_url='login')
def admin_approve_investment(request, payment_id):
    pay = get_object_or_404(InvestmentPayment, id=payment_id)
    if pay.status == 'PENDING':
        pay.status = 'COMPLETED'
        pay.save()
        
        # Update user's active plan
        profile = pay.user.profile
        profile.active_plan = pay.plan_name
        # Auto-enable signals if it's a high tier
        if pay.plan_name in ['Premium', 'Enterprise', 'Platinum', 'Ultimate']:
            profile.has_signal_subscription = True
            profile.has_ai_subscription = True
        profile.save()
        
        messages.success(request, f"Investment for {pay.user.username} approved.")
    return redirect('custom_admin_investments')

@staff_member_required(login_url='login')
def admin_reject_investment(request, payment_id):
    pay = get_object_or_404(InvestmentPayment, id=payment_id)
    if pay.status == 'PENDING':
        pay.status = 'REJECTED'
        pay.save()
        messages.error(request, f"Investment payment for {pay.user.username} rejected.")
    return redirect('custom_admin_investments')

def admin_toggle_service(request, user_id, service_type):
    profile = get_object_or_404(UserProfile, user__id=user_id)
    if service_type == 'signal':
        profile.has_signal_subscription = not profile.has_signal_subscription
    elif service_type == 'ai':
        profile.has_ai_subscription = not profile.has_ai_subscription
    elif service_type == 'block':
        profile.is_blocked = not profile.is_blocked
    elif service_type == 'suspend':
        profile.is_suspended = not profile.is_suspended
    profile.save()
    messages.success(request, f"Service updated for {profile.user.username}")
    return redirect('custom_admin_user_detail', user_id=user_id)
