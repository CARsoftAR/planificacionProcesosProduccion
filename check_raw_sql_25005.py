"""
Check raw SQL results for project 25-005
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.db import connections

sql = """
    SELECT TOP 10
        T.Formula,
        T2.Formula AS ProyectoCode,
        T.Mstnmbr,
        T.Idorden,
        T.Articulo,
        Isnull(T.Idmaquina, '') AS Idmaquina,
        MAC.MAQUINAD,
        T3.QMaquina
    FROM Tman050 T
    INNER JOIN tman050 T2 ON T.MSTNMBR = T2.IdOrden
    LEFT JOIN TMAN002 T3 ON 
        T.Articulo = T3.ArticuloH AND 
        T.Formula = T3.Formula AND 
        T2.Articulo = T3.ArticuloP
    LEFT JOIN Tman010 MAC ON 
        T.Idmaquina = MAC.Idmaquina
    WHERE T2.Formula LIKE '%25-005%' OR T.Formula LIKE '%25-005%'
"""

print("=" * 80)
print("RAW SQL RESULTS FOR PROJECT 25-005")
print("=" * 80)

with connections['production'].cursor() as cursor:
    cursor.execute(sql)
    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    
    print(f"\nColumns: {columns}\n")
    
    for i, row in enumerate(rows, 1):
        print(f"Row {i}:")
        for col, val in zip(columns, row):
            print(f"  {col}: {val}")
        print()
