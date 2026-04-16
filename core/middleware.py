from django.shortcuts import redirect
from django.urls import reverse

class AccountStatusMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                profile = request.user.profile
                # Check for Suspension
                if profile.is_suspended:
                    allowed_urls = [
                        reverse('suspended_page'),
                        reverse('logout'),
                        # Admin can still access admin pages if they are suspended? 
                        # Probably not, but staff should be careful.
                    ]
                    # Don't redirect if we are already on an allowed page
                    if request.path not in allowed_urls and not request.path.startswith('/et-admin/'):
                        return redirect('suspended_page')
            except:
                pass
        else:
            # Login Requirement for all pages except auth/static/public
            exempt_urls = [
                reverse('login'),
                reverse('signup'),
                reverse('terms'),
                reverse('privacy'),
                reverse('forgot_password'),
                reverse('suspended_page'),
            ]
            if request.path not in exempt_urls and not request.path.startswith('/static/'):
                return redirect('login')
        
        response = self.get_response(request)
        return response
