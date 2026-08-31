import os
import sys
import django
sys.path.append(r"c:\Sistemas ABBAMAT\planificacionProcesosProductivos EN DESARROLLO")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "planificacion.settings")
django.setup()

from produccion.models import PrioridadManual
# Check all recent PrioridadManual entries to see what percentage is there
pms = PrioridadManual.objects.filter(porcentaje_solapamiento__gt=0)
print(f"Found {pms.count()} records with solapamiento > 0:")
for pm in pms:
    print(f"ID Orden: {pm.id_orden} | Modo: {pm.modo_solapamiento} | %: {pm.porcentaje_solapamiento}")

# Let's also check if any sequence is being generated with 'porcentaje_solapamiento'
