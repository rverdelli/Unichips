@echo off
title San Carlo - Demo Avvio
color 0F
echo.
echo  ============================================
echo   SAN CARLO - Chatbot Demo - Avvio
echo  ============================================
echo.
echo  NOTA: Per abilitare CarloBot con AI reale puoi:
echo    1. Impostare la variabile d'ambiente ANTHROPIC_API_KEY prima di avviare
echo       (es: set ANTHROPIC_API_KEY=sk-ant-...)
echo    2. Oppure inserirla nel pannello Admin dopo l'avvio (icona ingranaggio)
echo.

if "%ANTHROPIC_API_KEY%"=="" (
    echo  [INFO] ANTHROPIC_API_KEY non impostata - demo in modalita offline
) else (
    echo  [OK] ANTHROPIC_API_KEY trovata - AI abilitata
)
echo.

:: -- Posizionati nella cartella dello script --
cd /d "%~dp0"

:: -- Verifica Python --
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRORE] Python non trovato nel PATH.
    echo          Installa Python 3.9+ da https://python.org e riprova.
    pause
    exit /b 1
)
echo [OK] Python trovato.

:: -- Crea venv se non esiste --
if not exist ".venv\Scripts\activate.bat" (
    echo Creazione virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERRORE] Impossibile creare il virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment creato.
)

call .venv\Scripts\activate.bat
echo [OK] Virtual environment attivato.

:: -- Installa dipendenze --
echo.
echo Installazione dipendenze...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [ERRORE] Installazione dipendenze fallita.
    pause
    exit /b 1
)
echo [OK] Dipendenze installate.

:: -- Init dati mock (solo se DB vuoto o assente) --
echo.
set DB_PATH=data\complaints.db
set ROW_COUNT=0
if exist "%DB_PATH%" (
    for /f %%i in ('.venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect('data/complaints.db'); print(c.execute('SELECT COUNT(*) FROM complaints').fetchone()[0])" 2^>nul') do set ROW_COUNT=%%i
)
if "%ROW_COUNT%"=="0" (
    echo Nessun dato trovato - inizializzazione dati mock...
    python init_data.py
) else (
    echo [OK] Database esistente con %ROW_COUNT% reclami - skip inizializzazione.
)

:: -- Avvia le app --
echo.
echo  ============================================
echo   Avvio applicazioni...
echo  ============================================
echo.
echo   Sito pubblico + CarloBot  ->  http://localhost:8000
echo   Dashboard Admin           ->  http://localhost:8000/admin
echo.
echo   Premi CTRL+C per fermare tutto.
echo  ============================================
echo.

:: Avvia FastAPI (sito pubblico + chatbot + admin dashboard)
start "San Carlo - Demo" cmd /c ".venv\Scripts\uvicorn.exe main:app --host 0.0.0.0 --port 8000 --reload"

:: Attendi avvio
echo Attendo avvio servizi...
timeout /t 5 /nobreak >nul

:: Apri browser
start "" "http://localhost:8000"
timeout /t 2 /nobreak >nul
start "" "http://localhost:8000/admin"

echo.
echo [OK] Demo avviata.
echo.
echo   Public:  http://localhost:8000
echo   Admin:   http://localhost:8000/admin
echo.
pause
