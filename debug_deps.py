import os
import django
import sys
import pprint

# Add parent directory to path to ensure modules are found
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.gantt_logic import get_gantt_data

class DummyRequest:
    def __init__(self):
        self.GET = {'proyectos': '26-021', 'run': '1', 'scenario_id': '4'}
        self.session = {}

if __name__ == "__main__":
    req = DummyRequest()
    print("Running get_gantt_data...")
    result = get_gantt_data(req, force_run=True)
    
    print("\n--- DEPENDENCY MAP ---")
    dep_map = getattr(result, 'dependency_map', {}) or result.get('dependency_map', {})
    for succ, preds in list(dep_map.items())[:10]:
        print(f"{succ} waits for {preds}")
    
    print("\n--- CHECKING TASK 47487 (VF2) ---")
    # Finding task in timeline
    tl = result.get('timeline_data', [])
    for row in tl:
        m = row['machine']
        m_name = getattr(m, 'nombre', '') if not isinstance(m, dict) else m.get('nombre', '')
        for t in row['tasks']:
            tid = str(t.get('Idorden'))
            if tid == "47487":
                print(f"FOUND 47487 on machine {m_name}")
                print(f"  Start: {t.get('start_date')}")
                print(f"  End: {t.get('end_date')}")
                print(f"  Duration Real: {t.get('duration_real')}")
            if tid == "47489" or tid == "47490":
                print(f"FOUND PRED {tid} on machine {m_name}")
                print(f"  Start: {t.get('start_date')}")
                print(f"  End: {t.get('end_date')}")
                print(f"  Duration Real: {t.get('duration_real')}")

