import math
from datetime import datetime

# Category decay mapping (Rule 5 & updated decay details)
CLUSTER_DECAY_MAPPING = {
    "financials": {"persistence": 0.8, "decay_rate": 0.005},
    "governance": {"persistence": 0.8, "decay_rate": 0.005},
    "compliance": {"persistence": 0.7, "decay_rate": 0.01},
    "operations": {"persistence": 0.7, "decay_rate": 0.01},
    "employment": {"persistence": 0.6, "decay_rate": 0.02},
    "product_tech": {"persistence": 0.5, "decay_rate": 0.05}
}

def parse_date_flexible(date_str):
    """
    Attempts to parse varying date formats into a datetime object.
    """
    clean_date = date_str.replace(' IST', '').strip()
    # Try ISO format first
    try:
        return datetime.fromisoformat(clean_date)
    except ValueError:
        pass
        
    for fmt in ('%B %d, %Y %I:%M %p', '%b %d, %Y %I:%M %p', '%B %d, %Y %H:%M', '%b %d, %Y %H:%M', '%Y-%m-%d', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(clean_date, fmt)
        except ValueError:
            continue
    return datetime.now()

def calculate_time_decay(strength, cluster_type, timestamp_str):
    """
    Applies the exponential decay formula: Decayed Strength = Strength * exp(-decay_rate * days_elapsed).
    Returns (decayed_strength, persistence, decay_rate).
    """
    dt = parse_date_flexible(timestamp_str)
    days_elapsed = (datetime.now() - dt).days
    if days_elapsed < 0:
        days_elapsed = 0

    # Get decay params
    params = CLUSTER_DECAY_MAPPING.get(cluster_type.strip().lower(), {"persistence": 0.6, "decay_rate": 0.02})
    persistence = params["persistence"]
    decay_rate = params["decay_rate"]

    # Calculate exponential decay
    decayed_strength = strength * math.exp(-decay_rate * days_elapsed)

    return round(decayed_strength, 3), persistence, decay_rate
