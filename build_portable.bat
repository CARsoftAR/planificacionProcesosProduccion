@echo off
setlocal
color 0A
echo ========================================================
echo        CONSTRUYENDO ABBAMAT PROD - MODO PORTABLE
echo ========================================================

REM Activar entorno virtual si existe
if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

echo [1/3] Limpiando cache e instalando pythonnet (Binario pre-compilado)...
pip cache purge
pip install --upgrade clr-loader pywebview pyinstaller
pip install pythonnet==3.0.1 --only-binary :all:

echo [2/3] Empaquetando con PyInstaller (--onedir)...
REM -y: Sobrescribir output previo
REM --windowed: No mostrar consola de Windows al ejecutar (solo GUI)
REM --add-data: Incluir plantillas y archivos estáticos
REM --hidden-import: Asegurar que apps de django no falten
echo [2/3] Empaquetando con PyInstaller usando desktop_run.spec...
pyinstaller --clean -y desktop_run.spec

echo [3/3] Copiando script de lanzamiento a la carpeta generada...
copy INICIAR_SISTEMA.bat dist\ABBAMAT_PROD_Desktop\

echo ========================================================
echo COMPILACION EXITOSA. 
echo La aplicacion empaquetada se encuentra en la carpeta:
echo dist\ABBAMAT_PROD_Desktop\
echo ========================================================
pause
