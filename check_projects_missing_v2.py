import os
import django
import sys
from django.db import connections

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

def check_projects(projects):
    print(f"--- REVISANDO PROYECTOS: {projects} ---")
    
    with connections['production'].cursor() as cursor:
        for p in projects:
            print(f"\nBuscando: '{p}'")
            # 1. Check if the project code exists as a 'Fórmula' (Project Code in ABBAMAT)
            sql_p = "SELECT IdOrden, Articulo, Descri, MSTNMBR, Formula FROM Tman050 WHERE Formula = %s"
            cursor.execute(sql_p, [p])
            rows = cursor.fetchall()
            print(f"Encontrados en Tman050 con Formula='{p}': {len(rows)}")
            
            for r in rows:
                id_orden, art, desc, mst, form = r
                print(f"  > ID Orden: {id_orden} | Art: {art} | MST: {mst} | Desc: {desc[:30]}")
                
                # if it's a project, it might have sub-orders where MSTNMBR = id_orden
                sql_ops = "SELECT COUNT(*) FROM Tman050 WHERE MSTNMBR = %s"
                cursor.execute(sql_ops, [id_orden])
                sub_ops = cursor.fetchone()[0]
                print(f"    - Sub-operaciones vinculadas (MSTNMBR={id_orden}): {sub_ops}")
                
                if sub_ops == 0:
                     # Maybe it's not a master, maybe it's just one operation. 
                     # Let's see if it has a Master that IS one of our projects.
                     sql_check_master = "SELECT Formula FROM Tman050 WHERE IdOrden = %s"
                     cursor.execute(sql_check_master, [mst])
                     master_row = cursor.fetchone()
                     if master_row:
                         print(f"    - Su Maestro tiene Formula: {master_row[0]}")

            # Also check for partial matches just in case
            sql_like = "SELECT TOP 3 Formula FROM Tman050 WHERE Formula LIKE %s"
            cursor.execute(sql_like, [f"%{p}%"])
            likes = cursor.fetchall()
            if likes:
                print(f"  Matches parciales (LIKE): {[l[0] for l in likes]}")

if __name__ == "__main__":
    check_projects(['25-074', '25-032'])
