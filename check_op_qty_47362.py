import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.db import connections

def check_op_quantity(op_id):
    sql = """
    SELECT 
        T.IdOrden as Task_OP,
        T.Articulo as Task_Articulo,
        T.Descri as Task_Desc,
        T.Cantidad as Task_Qty,
        T.Cantidadpp as Task_Prod,
        T2.IdOrden as Master_OP,
        T2.Articulo as Master_Articulo,
        T2.Descri as Master_Desc,
        T2.Cantidad as Master_Qty,
        T2.Formula as ProjectCode
    FROM Tman050 T
    INNER JOIN tman050 T2 ON T.MSTNMBR = T2.IdOrden
    WHERE T.IdOrden = %s
    """
    
    with connections['production'].cursor() as cursor:
        cursor.execute(sql, [op_id])
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        if not rows:
            print(f"No records found for OP {op_id}")
            return
            
        for row in rows:
            print(f"--- Data for OP {op_id} ---")
            for k, v in row.items():
                print(f"{k}: {v}")

if __name__ == "__main__":
    check_op_quantity('47362')
