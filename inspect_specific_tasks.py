import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.services import get_planificacion_data

ids = ['47268', '47391', '47380', '47362', '47375', '47368', '47267', '47244', '47390', '47379', '47260', '47374']
data = get_planificacion_data({'id_orden_in': ids})
for t in data:
    print(f"ID: {t['Idorden']} | Art: {t['Articulo']} | Nivel: {t['Nivel']} | NivelPlan: {t['Nivel_Planificacion']} | Desc: {t['Descri']}")
