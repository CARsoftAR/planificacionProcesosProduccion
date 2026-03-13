import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.db import connections

def check_types():
    sql = "SELECT TOP 1 Vto, Vto FROM Tman050" # Just to get a row
    with connections['production'].cursor() as cursor:
        cursor.execute("SELECT TOP 1 Vto FROM Tman050 WHERE Vto IS NOT NULL")
        row = cursor.fetchone()
        print(f"Type of Vto: {type(row[0])}")

if __name__ == "__main__":
    check_types()
