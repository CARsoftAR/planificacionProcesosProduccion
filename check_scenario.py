import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()
from produccion.models import Scenario, PlannedTask
s = Scenario.objects.filter(es_principal=True).first()
if s:
    print(f'Projects in scenario: "{s.proyectos}"')
    print(f'Total PlannedTask: {PlannedTask.objects.filter(scenario=s).count()}')
else:
    print('No principal scenario')
