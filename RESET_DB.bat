@echo off
title San Carlo - Reset Database
color 0C
echo.
echo  ============================================
echo   SAN CARLO - Reset Database
echo  ============================================
echo.
echo  ATTENZIONE: questa operazione cancella tutti i reclami
echo  e reinizializza il database con i dati di esempio.
echo.
set /p confirm="Sei sicuro? Digita SI per confermare: "
if /i not "%confirm%"=="SI" (
    echo Operazione annullata.
    pause
    exit /b 0
)

cd /d "%~dp0"

:: Elimina il database
if exist "data\complaints.db" (
    del /f "data\complaints.db"
    echo [OK] Database eliminato.
) else (
    echo [INFO] Nessun database trovato.
)

:: Reinizializza con i dati mock
if exist ".venv\Scripts\python.exe" (
    echo Reinizializzazione dati mock...
    .venv\Scripts\python.exe init_data.py
    echo [OK] Database reinizializzato.
) else (
    echo [WARN] Virtual environment non trovato - avvia prima START_DEMO.bat
)

echo.
echo  Database resettato con successo.
echo.
pause
