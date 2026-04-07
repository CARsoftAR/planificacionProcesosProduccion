import os
import django
import json
from datetime import datetime, date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.services import get_planificacion_data

def s(o): 
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    return str(o)

def run():
    ids = ['47659', '47649', '47658', '47648', '47647', '47656', '47652', '47655']
    results = get_planificacion_data({'id_orden_in': ids}, exclude_completed=False)
    print(json.dumps(results, indent=2, default=s))

if __name__ == "__main__":
    run()
