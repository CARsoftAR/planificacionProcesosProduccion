import os
import django
from django.conf import settings
from django.test import RequestFactory

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.gantt_logic import get_gantt_data
from produccion.models import PrioridadManual

def debug_export():
    print("--- DIAGNOSTIC START ---")
    
    # 1. Check DB directly
    try:
        pm = PrioridadManual.objects.get(id_orden=2654)
        print(f"DB CHECK: PrioridadManual for 2654 exists. Machine: '{pm.maquina}'")
    except PrioridadManual.DoesNotExist:
        print("DB CHECK: PrioridadManual for 2654 DOES NOT EXIST.")

    # 2. Simulate Request
    factory = RequestFactory()
    # Simulate params as if exporting (assuming user might have filtered project S15-041 or similar)
    # The user image shows Filter "DMG 800V" in Excel title? No, that's just a cell selected.
    # We will simulate a run without filters first, then with project filter.
    
    request = factory.get('/api/export_excel/?run=1')
    
    print("\n--- RUNNING get_gantt_data ---")
    data = get_gantt_data(request, force_run=True)
    
    timeline = data['timeline_data']
    
    # Find where 2654 ended up
    found = False
    for row in timeline:
        machine = row['machine']
        for t in row['tasks']:
            if str(t.get('Idorden')) == '2654':
                print(f"RESULT: Task 2654 found in machine: {machine.nombre} ({machine.id_maquina})")
                found = True
    
    if not found:
        print("RESULT: Task 2654 NOT FOUND in any machine in the output.")

debug_export()
