"""
Script de diagnóstico simple para verificar el pinning manual
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import PrioridadManual

print("=" * 70)
print("DIAGNOSTICO DEL SISTEMA DE PINNING MANUAL")
print("=" * 70)

# Verificar campos del modelo
print("\n1. CAMPOS DEL MODELO:")
fields = [f.name for f in PrioridadManual._meta.get_fields()]
print(f"Campos: {', '.join(fields)}")

if 'fecha_inicio_manual' in fields:
    print("[OK] Campo 'fecha_inicio_manual' existe")
else:
    print("[ERROR] Campo 'fecha_inicio_manual' NO existe")

# Verificar datos
print("\n2. DATOS EN LA BASE DE DATOS:")
total = PrioridadManual.objects.using('default').count()
print(f"Total registros: {total}")

with_dates = PrioridadManual.objects.using('default').filter(
    fecha_inicio_manual__isnull=False
).count()
print(f"Con fecha manual: {with_dates}")

if with_dates > 0:
    print("\nTareas con pinning:")
    for pm in PrioridadManual.objects.using('default').filter(
        fecha_inicio_manual__isnull=False
    )[:10]:
        print(f"  Orden {pm.id_orden} -> {pm.fecha_inicio_manual} (Maquina: {pm.maquina})")
else:
    print("[ADVERTENCIA] No hay tareas con pinning manual")

print("\n" + "=" * 70)
print("INSTRUCCIONES:")
print("1. Inicia el servidor: python manage.py runserver")
print("2. Abre el Gantt Visual con ?proyectos=XXX&run=1")
print("3. Arrastra una tarea a una nueva posicion")
print("4. Observa la consola del servidor (busca mensajes con emojis)")
print("5. Ejecuta este script nuevamente para verificar")
print("=" * 70)
