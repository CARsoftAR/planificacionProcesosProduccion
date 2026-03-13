import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.db import connections

def get_all_cols(op_id):
    sql = "SELECT * FROM Tman050 WHERE IdOrden = %s"
    with connections['production'].cursor() as cursor:
        cursor.execute(sql, [op_id])
        cols = [c[0] for c in cursor.description]
        row = cursor.fetchone()
        if row:
            print(f"Columns for {op_id}:")
            for k, v in dict(zip(cols, row)).items():
                print(f"  {k}: {v}")
        else:
            print(f"No data for {op_id}")

if __name__ == "__main__":
    get_all_cols('47379')
