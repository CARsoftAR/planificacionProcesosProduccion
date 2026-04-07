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
    print("="*60)
    print("ANALISIS TSUGAMI (PROD + REASIGNACIONES)")
    print("="*60)
    
    # Intentar usar el cursor de 'production'
    try:
        with connections['production'].cursor() as cursor:
            # En MSSQL la vista podria llamarse diferente o estar en un esquema
            cursor.execute("""
                SELECT maquina, COUNT(*) 
                FROM vw_planificacion_pendientes 
                WHERE maquina LIKE '%SUGAMI%'
                GROUP BY maquina
            """)
            results = cursor.fetchall()
            for m, count in results:
                print(f" >>> {m}: {count} tareas pendientes en PRODUCCION <<<")
    except Exception as e:
        print(f"Error al consultar MSSQL: {e}")

    # Tambien chequear PrioridadManual (SQLite)
    from produccion.models import PrioridadManual, Scenario, MaquinaConfig
    principal = Scenario.objects.filter(es_principal=True).first()
    if principal:
        overrides = PrioridadManual.objects.filter(scenario=principal)
        print(f"\nREASIGNACIONES (PrioridadManual) EN ESCENARIO PRINCIPAL ({principal.nombre}):")
        
        for o in overrides:
             m_name = "N/A"
             try: m_name = MaquinaConfig.objects.get(id_maquina=o.id_maquina).nombre
             except: pass
             
             if 'SUGAMI' in m_name.upper() or o.id_maquina == 'MAC38':
                 print(f" - Idorden: {o.id_orden} | Reasignada A: {m_name} ({o.id_maquina})")
             else:
                 # Check if the original machine for this task was Tsugami? 
                 # We can't know for sure here without joining production data.
                 pass
             
if __name__ == "__main__":
    count_tasks_per_machine()
