import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.db import connections

def check_op(op_id):
    sql = "SELECT IdOrden, Cantidad, Lote, Cantidadpp FROM Tman050 WHERE IdOrden = %s"
    with connections['production'].cursor() as cursor:
        cursor.execute(sql, [op_id])
        cols = [c[0] for c in cursor.description]
        row = cursor.fetchone()
        if row:
            print(f"Data for {op_id}: {dict(zip(cols, row))}")
        else:
            print(f"No data for {op_id}")

if __name__ == "__main__":
    check_op('47379')
    check_op('47390')
    check_op('47487')
