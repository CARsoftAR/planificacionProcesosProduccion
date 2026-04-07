import os
import django
import sys
from django.db import connections

current_dir = os.getcwd()
if current_dir not in sys.path:
    sys.path.append(current_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

def count_tasks_per_machine():
    # USAMOS SQL DIRECTO PARA RAPIDEZ SOBRE LA VISTA DE PLANIFICACION
    # O el modelo si existe
    with connections['default'].cursor() as cursor:
        cursor.execute("""
            SELECT maquina, COUNT(*) 
            FROM vw_planificacion_pendientes 
            GROUP BY maquina
        """)
        results = cursor.fetchall()
        print("CONTEO DE TAREAS PENDIENTES POR MAQUINA (vw_planificacion_pendientes):")
        for m, count in results:
            print(f" - {m}: {count} tareas")

    # Tambien chequear PrioridadManual (Overrrides)
    from produccion.models import PrioridadManual, Scenario
    principal = Scenario.objects.filter(es_principal=True).first()
    if principal:
        overrides = PrioridadManual.objects.filter(escenario=principal)
        print(f"\nOVERRIDES EN ESCENARIO PRINCIPAL ({principal.nombre}):")
        for o in overrides[:10]:
             print(f" - Idorden: {o.id_orden} | Machine: {o.id_maquina} | Priority: {o.prioridad}")

if __name__ == "__main__":
    count_tasks_per_machine()
