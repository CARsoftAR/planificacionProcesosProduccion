import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.db import connections

def check_3001_machines():
    sql = """
    SELECT 
        T2.Formula as Proyecto,
        T.Idorden,
        T.Idmaquina,
        MAC.MAQUINAD,
        T2.Vto as VtoProj
    FROM Tman050 T
    INNER JOIN Tman050 T2 ON T.MSTNMBR = T2.IdOrden
    LEFT JOIN Tman010 MAC ON T.Idmaquina = MAC.Idmaquina
    WHERE T2.Vto >= '2026-01-30' AND T2.Vto < '2026-01-31'
      AND T2.Formula = '26-002'
    """
    with connections['production'].cursor() as cursor:
        cursor.execute(sql)
        for row in cursor.fetchall():
            print(row)

if __name__ == "__main__":
    check_3001_machines()
