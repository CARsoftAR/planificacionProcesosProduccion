import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.db import connections

def find_by_vto(date_str):
    sql = """
    SELECT TOP 10
        T2.Formula as Proyecto,
        T.Idorden,
        T.Vto,
        T.Descri
    FROM Tman050 T
    INNER JOIN Tman050 T2 ON T.MSTNMBR = T2.IdOrden
    WHERE CAST(T.Vto AS DATE) = %s
    """
    with connections['production'].cursor() as cursor:
        cursor.execute(sql, [date_str])
        for row in cursor.fetchall():
            print(row)

if __name__ == "__main__":
    print("Searching for tasks due on 2025-12-22:")
    find_by_vto('2025-12-22')
