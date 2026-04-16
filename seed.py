import os
import sys

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'empiretrade.settings')
    import django
    django.setup()

    from core.models import Asset
    from django.contrib.auth.models import User

    # Create Superuser if not exists
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'admin')
        print("Created superuser 'admin' with password 'admin'")

    assets_data = [
        {
            'name': 'Bitcoin', 'symbol': 'BTC', 'icon_class': 'fab fa-bitcoin',
            'deposit_address': '1KMu1aYqv1N1Jn8YEqDYgAEYyVUnmieQm',
            'network': 'BTC',
            'current_price': 68450.20, 'change_24h': 2.15,
            'high_24h': 69120.00, 'low_24h': 67400.00, 'volume_24h': 1320000000000
        },
        {
            'name': 'Ethereum', 'symbol': 'ETH', 'icon_class': 'fab fa-ethereum',
            'deposit_address': '0x73265524c5f9390fa731d72a3565b034a7c2e254',
            'network': 'Ethereum (ERC20)',
            'current_price': 3450.85, 'change_24h': -1.12,
            'high_24h': 3550.00, 'low_24h': 3420.00, 'volume_24h': 412000000000
        },
        {
            'name': 'Solana', 'symbol': 'SOL', 'icon_class': 'fas fa-circle-nodes',
            'deposit_address': '6Vhwben czvW4QWfdqqQXN8nK9hHEaB Gh46RGWP5fVeaN',
            'network': 'SOL',
            'current_price': 145.20, 'change_24h': 5.42,
            'high_24h': 148.00, 'low_24h': 138.00, 'volume_24h': 64000000000
        },
        {
            'name': 'Ripple', 'symbol': 'XRP', 'icon_class': 'fas fa-coins',
            'deposit_address': 'rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh',
            'network': 'XRP',
            'memo_tag': '503240508',
            'current_price': 0.62, 'change_24h': -0.45,
            'high_24h': 0.64, 'low_24h': 0.61, 'volume_24h': 34000000000
        },
        {
            'name': 'Cardano', 'symbol': 'ADA', 'icon_class': 'fas fa-hexagon-nodes',
            'deposit_address': 'addr1v8h6dx6n5xnkvhprytweur4vc6j3ujl nOfwOm8smdhv2v8caylddh',
            'network': 'ADA',
            'current_price': 0.45, 'change_24h': 1.20,
            'high_24h': 0.48, 'low_24h': 0.42, 'volume_24h': 12000000000
        },
        {
            'name': 'Tether (USDT)', 'symbol': 'USDT', 'icon_class': 'fas fa-dollar-sign',
            'deposit_address': '0x73265524c5f9390fa731d72a3565b034a7c2e254',
            'network': 'Ethereum (ERC20)',
            'current_price': 1.00, 'change_24h': 0.01,
            'high_24h': 1.001, 'low_24h': 0.999, 'volume_24h': 812000000000
        },
    ]

    for data in assets_data:
        Asset.objects.update_or_create(
            symbol=data['symbol'],
            defaults=data
        )
    print("Seeded database with initial assets and unique deposit addresses.")

if __name__ == '__main__':
    main()
