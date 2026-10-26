"""Отправка писем по шаблонам `templates/<base>_subject.txt` + `<base>.txt` (+ необязательный `<base>.html`)."""
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string


def send_templated_mail(to, template_base, context):
    context = {"site_url": settings.SITE_URL, "project": "ГДеволна", **context}
    subject = " ".join(render_to_string(f"{template_base}_subject.txt", context).split())
    body = render_to_string(f"{template_base}.txt", context)
    message = EmailMultiAlternatives(subject=subject, body=body, from_email=settings.DEFAULT_FROM_EMAIL,
                                     to=[to] if isinstance(to, str) else list(to))
    try:
        message.attach_alternative(render_to_string(f"{template_base}.html", context), "text/html")
    except TemplateDoesNotExist:
        pass
    message.send()
