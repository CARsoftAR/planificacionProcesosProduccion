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
def divide(value, arg):
    """Divides the value by the arg"""
    try:
        f_arg = float(arg)
        if f_arg == 0:
            return 0
        return float(value) / f_arg
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
    """
    Generates a visually distinct hex color for each project code.
    
    Uses a golden-ratio hue distribution to maximize visual separation
    between any two projects, even with similar names like '26-002' and '26-003'.
    
    The golden angle (~137.5°) ensures consecutive indices are spread
    maximally around the 360° color wheel.
    """
    if not value:
        return "#3b82f6" # Default Blue
    
    value = str(value).strip()
    
    # Step 1: Generate a robust hash that amplifies small differences.
    # We use multiple rounds of mixing to decorrelate similar inputs.
    hash_val = 5381
    for i, char in enumerate(value):
        # Mix position into hash to differentiate "26-002" from "26-020"
        hash_val = ((hash_val * 33) ^ ord(char) ^ (i * 7)) & 0xFFFFFFFF
    # Extra mixing rounds (avalanche effect)
    hash_val = ((hash_val ^ (hash_val >> 16)) * 0x45d9f3b) & 0xFFFFFFFF
    hash_val = ((hash_val ^ (hash_val >> 13)) * 0x119de1f3) & 0xFFFFFFFF
    hash_val = (hash_val ^ (hash_val >> 16)) & 0xFFFFFFFF
    
    # Step 2: Use golden ratio to distribute hue evenly
    GOLDEN_RATIO = 0.618033988749895
    hue = ((hash_val * GOLDEN_RATIO) % 1.0) * 360.0
    
    # Step 3: Vary saturation and lightness slightly for more variety
    saturation = 70 + (hash_val % 25)       # 70-94%
    lightness  = 38 + ((hash_val >> 8) % 15) # 38-52%
    
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
    
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

