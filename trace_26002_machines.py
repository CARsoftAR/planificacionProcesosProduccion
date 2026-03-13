import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.db import connections

def check_machines_26002():
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
    WHERE T2.Formula = '26-002'
    """
    with connections['production'].cursor() as cursor:
        cursor.execute(sql)
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        for row in rows:
            print(f"Order: {row['Idorden']} | VtoP: {row['VtoProj']} | Machine ID: {row['Idmaquina']} | Machine Name: {row['MAQUINAD']}")

if __name__ == "__main__":
    check_machines_26002()
