@echo off
cd /d "%~dp0"
setlocal
color 0A
echo ========================================================
echo        CONSTRUYENDO ABBAMAT PROD - MODO PORTABLE
echo ========================================================

REM Activar entorno virtual si existe
if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

echo [1/3] Limpiando cache e instalando pythonnet...
pip cache purge
pip install --upgrade clr-loader pywebview pyinstaller
pip install "pythonnet>=3.0.3"

echo [2/3] Empaquetando con PyInstaller (--onedir)...
REM Limpieza de cache y directorios previos de forma protegida
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo [2/3] Empaquetando con PyInstaller usando desktop_run.spec...
pyinstaller --clean -y "desktop_run.spec"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================================
    echo   ERROR: El comando PyInstaller fallo.
    echo   Revisa los mensajes de error mostrados arriba.
    echo ========================================================
    pause
    exit /b %ERRORLEVEL%
)

echo [3/3] Copiando script de lanzamiento a la carpeta generada...
if not exist "dist\ABBAMAT_PROD_Desktop" mkdir "dist\ABBAMAT_PROD_Desktop"
copy /y "INICIAR_SISTEMA.bat" "dist\ABBAMAT_PROD_Desktop\"

echo ========================================================
echo COMPILACION EXITOSA. 
echo La aplicacion empaquetada se encuentra en la carpeta:
echo dist\ABBAMAT_PROD_Desktop\
echo ========================================================
pause
