import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.services import get_planificacion_data

data = get_planificacion_data({'proyectos': ['26-021']})
for t in data:
    print(f"ID: {t['Idorden']} | Art: {t['Articulo']} | Nivel: {t['Nivel']} | NivelPlan: {t['Nivel_Planificacion']} | Desc: {t['Descri']}")
