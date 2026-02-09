"""
Check machine codes vs descriptions
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import MaquinaConfig

print("=" * 80)
print("MACHINE CODES vs DESCRIPTIONS (Filtered for NLX)")
print("=" * 80)

machines = MaquinaConfig.objects.all()

for m in machines:
    if 'NLX' in m.nombre or '40' in m.id_maquina:
        print(f"Code: {m.id_maquina} | Name: {m.nombre}")
        for h in m.horarios.all():
            print(f"  -> {h.dia}: {h.hora_inicio} - {h.hora_fin}")
