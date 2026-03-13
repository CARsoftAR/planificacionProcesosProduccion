
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.services import get_planificacion_data

# Check task 47424 from DMG 800V
tasks = get_planificacion_data({'id_orden': '47424'})
if tasks:
    t = tasks[0]
    print(f"ID: {t.get('Idorden')}")
    print(f"Cantidad (T50): {t.get('Cantidad')}")
    print(f"Cantidad BOM (T3): {t.get('Cantidad_BOM')}")
    print(f"Lote: {t.get('Lote')}")
    print(f"Cantidad Final: {t.get('Cantidad_Final')}")
    print(f"Cantidad Prod: {t.get('Cantidadpp')}")
    print(f"Cantidades Pendientes: {t.get('CantidadesPendientes')}")
else:
    print("Task 47424 not found")

# Check task 47122 from the user's first image
tasks2 = get_planificacion_data({'id_orden': '47122'})
if tasks2:
    t = tasks2[0]
    print(f"\nID: {t.get('Idorden')}")
    print(f"Cantidad Final: {t.get('Cantidad_Final')}")
    print(f"Cantidad Prod: {t.get('Cantidadpp')}")
    print(f"Cantidades Pendientes: {t.get('CantidadesPendientes')}")
    print(f"Tiempo Proceso: {t.get('Tiempo_Proceso')}")
