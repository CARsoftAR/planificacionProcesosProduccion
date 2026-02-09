import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import PrioridadManual

print("--- Checking Manual Dates in DB ---")
entries = PrioridadManual.objects.filter(fecha_inicio_manual__isnull=False)
count = entries.count()
print(f"Total entries with manual start: {count}")

for e in entries:
    print(f"ID Orden: {e.id_orden} | Found in DB: {e.fecha_inicio_manual} (Type: {type(e.fecha_inicio_manual)})")

if count == 0:
    print("NO MANUAL DATES FOUND! The frontend might not be saving them, or your move didn't work.")
