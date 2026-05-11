#!/bin/sh

# Salir si hay errores
set -e

echo "🚀 Iniciando Preparación del Servidor..."

# Ejecutar migraciones
echo "📂 Aplicando migraciones..."
python manage.py migrate --noinput

# Recolectar archivos estáticos (opcional si usas WhiteNoise o similar)
# echo "🎨 Recolectando archivos estáticos..."
# python manage.py collectstatic --noinput

# Iniciar servidor
echo "🔥 Arrancando Gunicorn..."
exec gunicorn planificacion.wsgi:application --bind 0.0.0.0:8000 --workers 3
