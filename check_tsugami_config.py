"""
Check TSUGAMI machine configuration in database.
"""
import os
import sys
import django

sys.path.insert(0, r'C:\Sistemas ABBAMAT\planificacionProcesosProductivos')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import MaquinaConfig

print("=" * 70)
print("TSUGAMI MACHINE CONFIGURATION")
print("=" * 70)

# Find TSUGAMI machines
maquinas = MaquinaConfig.objects.using('default').all()

for m in maquinas:
    if 'TSUGAMI' in m.nombre.upper():
        print(f"\nMachine: {m.nombre} (ID: {m.id_maquina})")
        print(f"  Horarios:")
        for h in m.horarios.all():
            print(f"    {h.dia}: {h.hora_inicio.strftime('%H:%M')} - {h.hora_fin.strftime('%H:%M')}")

# Also show all machines with their max schedule hours
print("\n" + "=" * 70)
print("ALL MACHINES SCHEDULE HOURS")
print("=" * 70)

for m in maquinas:
    max_end = None
    for h in m.horarios.all():
        if max_end is None or h.hora_fin.hour > max_end:
            max_end = h.hora_fin.hour
    print(f"{m.nombre}: max_end = {max_end}")
