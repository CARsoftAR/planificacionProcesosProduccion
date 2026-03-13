import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.db import connections

def check_master_tasks(master_id):
    sql = """
    SELECT 
        T.IdOrden as Task_OP,
        T.Articulo as Task_Articulo,
        T.Descri as Task_Desc,
        T.Cantidad as Task_Qty,
        T.Cantidadpp as Task_Prod,
        T.IdEstado,
        MAC.MAQUINAD
    FROM Tman050 T
    LEFT JOIN Tman010 MAC ON T.Idmaquina = MAC.Idmaquina
    WHERE T.MSTNMBR = %s
    ORDER BY T.IdOrden
    """
    
    with connections['production'].cursor() as cursor:
        cursor.execute(sql, [master_id])
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        print(f"--- Tasks for Master OP {master_id} ---")
        for row in rows:
            print(f"OP: {row['Task_OP']} | Art: {row['Task_Articulo']} | Qty: {row['Task_Qty']} | Machine: {row['MAQUINAD']} | Desc: {row['Task_Desc']}")

if __name__ == "__main__":
    check_master_tasks('47355')
