import sys
import os

# 1. Force the project root into the path
BASE_DIR = os.path.dirname(__file__)
sys.path.insert(0, BASE_DIR)

# 2. Add the inner settings folder to path
sys.path.insert(0, os.path.join(BASE_DIR, 'empiretrade'))

# 3. Set the settings module
os.environ['DJANGO_SETTINGS_MODULE'] = 'empiretrade.settings'

# 4. Import the Django WSGI application
try:
    from empiretrade.wsgi import application
except Exception:
    import traceback
    def application(environ, start_response):
        start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
        return [traceback.format_exc().encode()]
