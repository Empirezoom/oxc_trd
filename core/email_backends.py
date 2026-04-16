import json
import requests
import ssl
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.smtp import EmailBackend

class RelaxedSMTPBackend(EmailBackend):
    """
    An SMTP backend that ignores SSL certificate verification and "weak key" errors.
    Useful for local testing with cPanel mail servers.
    """
    @property
    def ssl_context(self):
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        # Allow old/weak keys
        context.set_ciphers('DEFAULT@SECLEVEL=1')
        return context

class SendGridAPIBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False):
        super().__init__(fail_silently=fail_silently)
        self.api_key = getattr(settings, 'SENDGRID_API_KEY', None)
        self.api_url = 'https://api.sendgrid.com/v3/mail/send'

    def send_messages(self, email_messages):
        if not self.api_key:
            if not self.fail_silently:
                raise ValueError('SENDGRID_API_KEY is not configured')
            return 0

        num_sent = 0
        for message in email_messages:
            try:
                sent = self._send(message)
                if sent:
                    num_sent += 1
            except Exception as e:
                if not self.fail_silently:
                    raise
        return num_sent

    def _send(self, message):
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        to_emails = [{'email': addr} for addr in message.to]
        content_type = 'text/html' if message.content_subtype == 'html' else 'text/plain'

        payload = {
            'personalizations': [{'to': to_emails}],
            'from': {'email': message.from_email},
            'subject': message.subject,
            'content': [{'type': content_type, 'value': message.body}],
        }
        if message.cc:
            payload['personalizations'][0]['cc'] = [{'email': addr} for addr in message.cc]
        if message.bcc:
            payload['personalizations'][0]['bcc'] = [{'email': addr} for addr in message.bcc]

        try:
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=10)
            if response.status_code == 202:
                return True
            else:
                error_msg = f'SendGrid API returned {response.status_code}: {response.text}'
                if self.fail_silently:
                    import logging
                    logging.error(error_msg)
                    return False
                else:
                    raise Exception(error_msg)
        except Exception as e:
            if self.fail_silently:
                import logging
                logging.exception('SendGrid API error: %s', e)
                return False
            else:
                raise
