import sys
import os
import django

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'empiretrade.settings')
django.setup()

from core.models import Asset

def update_addresses():
    data = [
        {
            'symbol': 'BTC',
            'network': 'BTC',
            'addr': '1KMu1aYqv1N1Jn8YEqDYgAEYyVUnmieeQm',
            'icon': 'https://cryptologos.cc/logos/bitcoin-btc-logo.png'
        },
        {
            'symbol': 'ETH',
            'network': 'Ethereum (ERC20)',
            'addr': '0x73265524c5f9390fa731d72a3565b034a7c2e254',
            'icon': 'https://cryptologos.cc/logos/ethereum-eth-logo.png'
        },
        {
            'symbol': 'SOL',
            'network': 'SOL',
            'addr': '6VhwbenczvW4QWfdqqQxN8nK9hHEaBGh46RGWP5fVeaN',
            'icon': 'https://cryptologos.cc/logos/solana-sol-logo.png'
        },
        {
            'symbol': 'ADA',
            'network': 'ADA',
            'addr': 'addr1v8h6dx6n5xnkvhprytweur4vc6j3ujln0fw0m8smdhv2v8caylddh',
            'icon': 'https://cryptologos.cc/logos/cardano-ada-logo.png'
        },
        {
            'symbol': 'USDT',
            'network': 'Ethereum (ERC20)',
            'addr': '0x73265524c5f9390fa731d72a3565b034a7c2e254',
            'icon': 'https://cryptologos.cc/logos/tether-usdt-logo.png'
        },
        {
            'symbol': 'XRP',
            'network': 'XRP',
            'addr': 'r4rjtVAtG3gmcDHU3nmXdYKcVSbvGPF7Fa',
            'memo': '503240508',
            'icon': 'https://cryptologos.cc/logos/xrp-xrp-logo.png'
        }
    ]

    for item in data:
        asset, created = Asset.objects.get_or_create(symbol=item['symbol'])
        asset.deposit_address = item['addr']
        asset.network = item['network']
        asset.icon_url = item.get('icon', '')
        if 'memo' in item:
            asset.memo_tag = item['memo']
        asset.save()
        print(f"Updated {item['symbol']} address to {item['addr']} on {item['network']}")

if __name__ == '__main__':
    update_addresses()
