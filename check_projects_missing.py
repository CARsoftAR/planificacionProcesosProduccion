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
            # First, check if the project code exists in Tman010 (Operations)
            sql_ops = "SELECT COUNT(*) FROM Tman010 WHERE Formula = %s"
            cursor.execute(sql_ops, [p])
            count_ops = cursor.fetchone()[0]
            print(f"Operaciones directas (Formula='{p}'): {count_ops}")
            
            # Second, check if it's a "ProyectoCode" (Tman010.Formula vs Tman010_2.Formula)
            # The query in services.py uses: T2.Formula AS ProyectoCode ... FROM Tman010 T JOIN Tman010 T2 ON T.Mstnmbr = T2.Mstnmbr
            # Let's see if we find it as a master number reference
            sql_master = "SELECT COUNT(*) FROM Tman010 WHERE Mstnmbr IN (SELECT Mstnmbr FROM Tman010 WHERE Formula = %s)"
            cursor.execute(sql_master, [p])
            count_master = cursor.fetchone()[0]
            print(f"Operaciones totales por Master Number (vía '{p}'): {count_master}")

            if count_master > 0:
                # Show some sample data
                sql_sample = "SELECT TOP 5 Formula, Idorden, Descri, Idmaquina FROM Tman010 WHERE Mstnmbr IN (SELECT Mstnmbr FROM Tman010 WHERE Formula = %s)"
                cursor.execute(sql_sample, [p])
                rows = cursor.fetchall()
                for r in rows:
                    print(f"  - OP: {r[1]} | Art: {r[0]} | Desc: {r[2]} | Maq: {r[3]}")

if __name__ == "__main__":
    check_projects(['25-074', '25-032'])
