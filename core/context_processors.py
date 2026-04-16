from decimal import Decimal
from .models import UserProfile

def currency_context(request):
    if not request.user.is_authenticated:
        return {'pref_symbol': '$', 'pref_currency': 'USD', 'currency_rate': Decimal('1.00')}
        
    try:
        profile = request.user.profile
        profile.check_plan_expiry() # Force check on every page load
        pref = profile.preferred_currency
    except:
        pref = 'USD'
        
    # Standard rates (Mocked for Demo)
    rates = {
        'USD': ('$', Decimal('1.00')),
        'NGN': ('₦', Decimal('1500.00')),
        'EUR': ('€', Decimal('0.92')),
        'GBP': ('£', Decimal('0.79')),
    }
    
    symbol, rate = rates.get(pref, ('$', Decimal('1.00')))
    
    return {
        'pref_symbol': symbol,
        'pref_currency': pref,
        'currency_rate': rate,
    }
