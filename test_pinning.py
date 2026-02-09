"""
Test script to verify the set_priority endpoint is working correctly.
"""
import requests
import json
from datetime import datetime

# Test data
task_id = 2658  # Use a real task ID from your system
machine_id = "MAC00"  # Use a real machine ID
manual_start = "2025-12-23 14:30:00"
priority = 5500

url = f"http://localhost:8000/api/set_priority/{task_id}/"

payload = {
    "maquina": machine_id,
    "new_priority": priority,
    "manual_start": manual_start
}

print(f"Testing endpoint: {url}")
print(f"Payload: {json.dumps(payload, indent=2)}")

try:
    response = requests.post(url, json=payload)
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")
