@echo off
setlocal
color 0B
echo ========================================================
echo        INICIANDO ABBAMAT PROD - MODO ESCRITORIO
echo ========================================================

REM Obtener directorio actual
set "BASE_DIR=%~dp0"
cd /d "%BASE_DIR%"

echo [1/3] Verificando entorno...

REM Verificamos si existe la base de datos de sqlite, si no lanzamos migración
if not exist "db.sqlite3" (
    echo [INFO] No se encontro db.sqlite3. Ejecutando migraciones iniciales...
    python manage.py migrate
)

echo [2/3] Preparando interfaz de escritorio...
echo [3/3] Abriendo ABBAMAT PROD... (por favor espera)

REM Iniciar la app usando Python en tiempo real para desarrollo (lee archivos directamente)
if exist "venv\Scripts\python.exe" (
    start "" "venv\Scripts\python.exe" desktop_run.py
) else (
    if exist "ABBAMAT_PROD_Desktop.exe" (
        start "" ABBAMAT_PROD_Desktop.exe
    ) else (
        start "" python desktop_run.py
    )
)

exit
