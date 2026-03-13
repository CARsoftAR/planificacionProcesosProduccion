import os
import django
import json
from datetime import datetime

# Setup Django
import sys
sys.path.append(r'c:\Sistemas ABBAMAT\planificacionProcesosProductivos')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.services import get_planificacion_data

def check_project_data(project_code):
    print(f"Checking data for project: {project_code}")
    data = get_planificacion_data({'proyectos': [project_code]})
    
    if not data:
        print("No data found.")
        return

    print(f"Found {len(data)} tasks.")
    
    vtos = []
    for t in data:
        vto = t.get('Vto')
        oid = t.get('Idorden')
        vtos.append((oid, vto))
        print(f"  OP {oid}: Vto={vto}")

    if vtos:
        max_vto = max(v[1] for v in vtos if v[1])
        min_vto = min(v[1] for v in vtos if v[1])
        print(f"\nSummary for {project_code}:")
        print(f"  Max Vto: {max_vto}")
        print(f"  Min Vto: {min_vto}")

if __name__ == "__main__":
    check_project_data('25-013')
    print("\n" + "="*40 + "\n")
    check_project_data('25-092')
