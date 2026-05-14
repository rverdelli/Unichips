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

:: -- Init dati mock --
echo.
echo Inizializzazione dati mock...
python init_data.py

:: -- Avvia le app --
echo.
echo  ============================================
echo   Avvio applicazioni...
echo  ============================================
echo.
echo   [1] Sito pubblico + CarloBot  ->  http://localhost:8000
echo   [2] Dashboard Admin           ->  http://localhost:8502
echo.
echo   Premi CTRL+C per fermare tutto.
echo  ============================================
echo.

:: Avvia FastAPI (sito pubblico + chatbot API)
start "San Carlo - Public (FastAPI)" cmd /c ".venv\Scripts\uvicorn.exe main:app --host 0.0.0.0 --port 8000 --reload"

:: Piccola pausa
timeout /t 3 /nobreak >nul

:: Avvia Streamlit admin
start "San Carlo - Admin Dashboard" cmd /c ".venv\Scripts\streamlit.exe run admin_app.py --server.port 8502 --server.headless true --browser.gatherUsageStats false"

:: Attendi avvio
echo Attendo avvio servizi...
timeout /t 6 /nobreak >nul

:: Apri browser
start "" "http://localhost:8000"
timeout /t 2 /nobreak >nul
start "" "http://localhost:8502"

echo.
echo [OK] Demo avviata.
echo.
echo   Public:  http://localhost:8000
echo   Admin:   http://localhost:8502
echo.
pause
