
import os
import django
import sys

# Setup Django
sys.path.append(r'c:\Sistemas ABBAMAT\planificacionProcesosProductivos')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.gantt_logic import get_gantt_data
from django.test import RequestFactory

def diagnose():
    factory = RequestFactory()
    # Mocking the request with the project that has issues
    request = factory.get('/planificacion/visual/?proyectos=25-087&scenario_id=1&plan_mode=manual')
    
    # We need to mock the session because get_gantt_data uses it
    from django.contrib.sessions.backends.db import SessionStore
    request.session = SessionStore()
    
    data = get_gantt_data(request)
    
    print("DIAGNOSTICS for Project 25-087 (SIN ASIGNAR row)")
    print("=" * 80)
    
    for row in data['timeline_data']:
        m = row['machine']
        m_name = getattr(m, 'nombre', 'Unknown')
        m_id = getattr(m, 'id_maquina', 'Unknown')
        
        if m_id == 'MAC00' or m_name == 'SIN ASIGNAR':
            print(f"Machine: {m_name} (ID: {m_id})")
            tasks = row['tasks']
            print(f"Total tasks: {len(tasks)}")
            
            for t in tasks:
                start = t.get('start_date')
                end = t.get('end_date')
                oid = t.get('Idorden')
                nivel = t.get('Nivel_Planificacion')
                pinned = t.get('is_pinned', False)
                
                print(f"Task {oid}: Level={nivel}, Start={start}, End={end}, Pinned={pinned}")
                
if __name__ == "__main__":
    diagnose()
