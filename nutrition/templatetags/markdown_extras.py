import markdown

from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter
def convert_markdown(value):
    return markdown.markdown(value, extensions=['markdown.extensions.fenced_code','markdown.extensions.tables'])