import os
import django
from django.utils import timezone
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()
from produccion.models import MantenimientoMaquina

print("MAINTENANCES:")
for m in MantenimientoMaquina.objects.all():
    print(f"- Maquina: {m.maquina_id} | Inicio: {m.fecha_inicio} | Fin: {m.fecha_fin} | Estado: {m.estado}")
