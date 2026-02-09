# -*- coding: utf-8 -*-
"""
Script para corregir la codificación de los feriados en la base de datos.
Ejecutar con: python fix_feriados_encoding.py
"""

import os
import sys
import django

# Configurar Django
sys.path.append(r'c:\Sistemas ABBAMAT\planificacionProcesosProductivos')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import Feriado
from datetime import date

# Feriados 2025 con codificación correcta
feriados_2025 = {
    date(2025, 1, 1): 'Año Nuevo',
    date(2025, 2, 24): 'Carnaval',
    date(2025, 2, 25): 'Carnaval',
    date(2025, 3, 24): 'Día Nacional de la Memoria por la Verdad y la Justicia',
    date(2025, 4, 2): 'Día del Veterano y de los Caídos en la Guerra de Malvinas',
    date(2025, 4, 18): 'Viernes Santo',
    date(2025, 5, 1): 'Día del Trabajador',
    date(2025, 5, 25): 'Día de la Revolución de Mayo',
    date(2025, 6, 16): 'Paso a la Inmortalidad del General Martín Miguel de Güemes',
    date(2025, 6, 20): 'Paso a la Inmortalidad del General Manuel Belgrano',
    date(2025, 7, 9): 'Día de la Independencia',
    date(2025, 8, 17): 'Paso a la Inmortalidad del General José de San Martín',
    date(2025, 10, 12): 'Día del Respeto a la Diversidad Cultural',
    date(2025, 11, 24): 'Día de la Soberanía Nacional',
    date(2025, 12, 8): 'Día de la Inmaculada Concepción de María',
    date(2025, 12, 18): 'Ejemplo',
    date(2025, 12, 24): 'Nochebuena (Medio día)',
    date(2025, 12, 25): 'Navidad',
    date(2025, 12, 31): 'Fin de Año (Medio día)',
}

# Feriados 2026 con codificación correcta
feriados_2026 = {
    date(2026, 1, 1): 'Año Nuevo',
    date(2026, 2, 16): 'Carnaval',
    date(2026, 2, 17): 'Carnaval',
    date(2026, 3, 24): 'Día Nacional de la Memoria por la Verdad y la Justicia',
    date(2026, 4, 2): 'Día del Veterano y de los Caídos en la Guerra de Malvinas',
    date(2026, 4, 3): 'Viernes Santo',
    date(2026, 5, 1): 'Día del Trabajador',
    date(2026, 5, 25): 'Día de la Revolución de Mayo',
    date(2026, 6, 17): 'Paso a la Inmortalidad del General Martín Miguel de Güemes',
    date(2026, 6, 20): 'Paso a la Inmortalidad del General Manuel Belgrano',
    date(2026, 7, 9): 'Día de la Independencia',
    date(2026, 8, 17): 'Paso a la Inmortalidad del General José de San Martín',
    date(2026, 10, 12): 'Día del Respeto a la Diversidad Cultural',
    date(2026, 11, 20): 'Día de la Soberanía Nacional',
    date(2026, 12, 8): 'Día de la Inmaculada Concepción de María',
    date(2026, 12, 25): 'Navidad',
}

# Combinar todos los feriados
todos_feriados = {**feriados_2025, **feriados_2026}

print("Corrigiendo codificación de feriados...")
print("=" * 70)

updated_count = 0
not_found_count = 0

for fecha, descripcion_correcta in todos_feriados.items():
    try:
        feriado = Feriado.objects.using('default').get(fecha=fecha)
        feriado.descripcion = descripcion_correcta
        feriado.save(using='default')
        updated_count += 1
        print(f"[OK] Actualizado: {fecha.strftime('%d/%m/%Y')} - {descripcion_correcta}")
    except Feriado.DoesNotExist:
        not_found_count += 1
        print(f"[X] No encontrado: {fecha.strftime('%d/%m/%Y')}")

print("=" * 70)
print(f"\nResumen:")
print(f"  - Feriados actualizados: {updated_count}")
print(f"  - Feriados no encontrados: {not_found_count}")
print(f"  - Total en base de datos: {Feriado.objects.using('default').count()}")
print("=" * 70)

print("\n¡Codificación corregida exitosamente!")
