def icinga2_priority(data):
    priority = 2 if data['payload'].startswith('Timeout for topic') else 0
    return priority

