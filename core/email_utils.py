from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags

def send_notification_email(user, subject, template_name, context=None):
    """
    Global helper to send styled emails.
    """
    if context is None:
        context = {}
    
    context['user'] = user
    context['site_name'] = getattr(settings, 'SITE_NAME', 'OctalX')
    
    html_content = render_to_string(f'emails/{template_name}', context)
    text_content = strip_tags(html_content)
    
    email = EmailMultiAlternatives(
        subject=f"[{settings.SITE_NAME}] {subject}",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email]
    )
    email.attach_alternative(html_content, "text/html")
    # Set to False so we can see the error message for debugging
    return email.send(fail_silently=False)
