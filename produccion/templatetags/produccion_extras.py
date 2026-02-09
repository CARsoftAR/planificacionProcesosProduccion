from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def multiply(value, arg):
    """Multiplies the arg and the value"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def time_diff_hours(value, arg):
    """Returns difference in hours between two datetimes (value - arg)"""
    try:
        diff = value - arg
        return diff.total_seconds() / 3600.0
    except (ValueError, TypeError):
        return 0

@register.filter
def string_to_color(value):
    """Generates a distinct hex color code from a string using HSL color space."""
    if not value:
        return "#0d6efd" # Default Blue
    
    # Generate hash from string
    hash_val = 0
    for char in str(value):
        hash_val = ord(char) + ((hash_val << 5) - hash_val)
    
    # Use hash to generate HSL values for pastel colors
    # Hue: 0-360 degrees (full color spectrum)
    hue = abs(hash_val) % 360
    
    # Saturation: 70-100% (vibrant colors)
    saturation = 70 + (abs(hash_val >> 8) % 30)
    
    # Lightness: 40-55% (darker colors for better visibility/contrast with white text)
    lightness = 40 + (abs(hash_val >> 16) % 15)
    
    # Convert HSL to RGB
    h = hue / 360.0
    s = saturation / 100.0
    l = lightness / 100.0
    
    def hue_to_rgb(p, q, t):
        if t < 0: t += 1
        if t > 1: t -= 1
        if t < 1/6: return p + (q - p) * 6 * t
        if t < 1/2: return q
        if t < 2/3: return p + (q - p) * (2/3 - t) * 6
        return p
    
    if s == 0:
        r = g = b = l
    else:
        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        r = hue_to_rgb(p, q, h + 1/3)
        g = hue_to_rgb(p, q, h)
        b = hue_to_rgb(p, q, h - 1/3)
    
    # Convert to hex
    r_hex = int(r * 255)
    g_hex = int(g * 255)
    b_hex = int(b * 255)
    
    return f"#{r_hex:02x}{g_hex:02x}{b_hex:02x}"

