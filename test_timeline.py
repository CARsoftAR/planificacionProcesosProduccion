from datetime import datetime, timedelta

def simulate():
    schedules = {'LV': [{'start': datetime.strptime("07:00", "%H:%M").time(), 'end': datetime.strptime("16:00", "%H:%M").time()}]}
    current_time = datetime.strptime("2025-04-23 13:20", "%Y-%m-%d %H:%M")
    remaining_hours = 7.83  # 7h 50m
    
    segments = []
    while remaining_hours > 0.001:
        s = schedules['LV'][0]['start']
        e = schedules['LV'][0]['end']
        
        current_time_time = current_time.time()
        if s <= current_time_time < e:
            available_seconds = (datetime.combine(current_time.date(), e) - current_time).total_seconds()
            available_hours = available_seconds / 3600.0
            
            time_to_consume = min(remaining_hours, available_hours)
            segment_start = current_time
            current_time = current_time + timedelta(hours=time_to_consume)
            
            # Snap to shift boundary
            if time_to_consume >= available_hours - 0.001:
                current_time = datetime.combine(current_time.date(), e)
                
            remaining_hours -= time_to_consume
            segments.append((segment_start, current_time, time_to_consume))
        else:
            # Advance to next day 07:00
            current_time = (current_time + timedelta(days=1)).replace(hour=7, minute=0, second=0)

    for seg in segments:
        print(f"Segment: {seg[0].strftime('%Y-%m-%d %H:%M')} to {seg[1].strftime('%Y-%m-%d %H:%M')} (Duration: {seg[2]:.2f}h)")

simulate()
