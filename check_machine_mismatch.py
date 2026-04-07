import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()
from produccion.models import MaquinaConfig
from django.db import connections

def check_mismatch():
    print("CONFIGURACION LOCAL (MaquinaConfig):")
    for m in MaquinaConfig.objects.all():
        print(f"- ID: '{m.id_maquina}' | Nombre: '{m.nombre}'")
    
    print("\nVALORES REALES EN ERP (SQL Server) para Bancos:")
    sql = "SELECT Idmaquina, MAQUINAD FROM Tman010 WHERE MAQUINAD LIKE '%BANCO%'"
    with connections['production'].cursor() as cursor:
        cursor.execute(sql)
        for row in cursor.fetchall():
            print(f"- ERP_ID: '{row[0]}' | ERP_Nombre: '{row[1]}'")

if __name__ == "__main__":
    check_mismatch()
