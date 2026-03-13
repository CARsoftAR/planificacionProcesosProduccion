import os
import django
import json
from unittest.mock import MagicMock

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.gantt_logic import get_gantt_data
from django.test import RequestFactory

factory = RequestFactory()
request = factory.get('/produccion/planificacion_visual/?run=1&proyectos=26-021')
request.session = {} # Mock session

print("Starting get_gantt_data...")
data = get_gantt_data(request)
print("Finished get_gantt_data.")
print(f"Number of rows: {len(data['timeline_data'])}")
print(f"Number of dependencies: {sum(len(v) for v in data['dependency_map'].values())}")
