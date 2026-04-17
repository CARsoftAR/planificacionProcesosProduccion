import os
import django
from django.db import connections

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

with connections['production'].cursor() as cursor:
    cursor.execute("SELECT TOP 1 * FROM v_tman")
    cols = [col[0] for col in cursor.description]
    print(cols)
