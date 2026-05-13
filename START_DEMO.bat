@echo off
title San Carlo - Demo Avvio
color 0F
echo.
echo  ============================================
echo   SAN CARLO - Chatbot Demo - Avvio
echo  ============================================
echo.

:: -- Posizionati nella cartella dello script --
cd /d "%~dp0"

:: -- Verifica Python --
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRORE] Python non trovato nel PATH.
    echo          Installa Python 3.9+ da https://python.org e riprova.
    echo.
    pause
    exit /b 1
)

echo [OK] Python trovato.

:: -- Crea venv se non esiste --
if not exist ".venv\Scripts\activate.bat" (
    echo.
    echo Creazione virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERRORE] Impossibile creare il virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment creato.
)

:: -- Attiva venv --
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
if errorlevel 1 (
    echo [ATTENZIONE] Errore nell'inizializzazione dati, continuo comunque...
)

:: -- Avvia le app --
echo.
echo  ============================================
echo   Avvio applicazioni...
echo  ============================================
echo.
echo   [1] Sito pubblico + Chatbot  ->  http://localhost:8501
echo   [2] Dashboard Admin          ->  http://localhost:8502
echo.
echo   Premi CTRL+C in questa finestra per fermare tutto.
echo  ============================================
echo.

:: Avvia app pubblica in background
start "San Carlo - Public App" cmd /c ".venv\Scripts\streamlit.exe run public_app.py --server.port 8501 --server.headless true --browser.gatherUsageStats false"

:: Piccola pausa per non sovraccaricare
timeout /t 3 /nobreak >nul

:: Avvia admin app in background
start "San Carlo - Admin App" cmd /c ".venv\Scripts\streamlit.exe run admin_app.py --server.port 8502 --server.headless true --browser.gatherUsageStats false"

:: Attendi che le app si avviino
echo Attendo avvio servizi...
timeout /t 5 /nobreak >nul

:: Apri browser
start "" "http://localhost:8501"
timeout /t 2 /nobreak >nul
start "" "http://localhost:8502"

echo.
echo [OK] Demo avviata. Lascia aperta questa finestra.
echo.
echo   Public:  http://localhost:8501
echo   Admin:   http://localhost:8502
echo.
pause
