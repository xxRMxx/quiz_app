from django import template

register = template.Library()

@register.filter
def int2char(value):
    """Convert integer to corresponding letter (1=A, 2=B, etc.)"""
    try:
        return chr(64 + int(value))  # 65 is ASCII for 'A'
    except (ValueError, TypeError):
        return ''

@register.filter
def sub(value, arg):
    """Subtract arg from value"""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return 0

@register.filter 
def percentage(value, total):
    """Calculate percentage"""
    try:
        if int(total) == 0:
            return 0
        return round((int(value) / int(total)) * 100, 1)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0