@echo off
REM ================================================================
REM  MIDNIGHT SCHEDULER - Uruchomienie lokalne
REM  Scraper startuje codziennie o 02:00 czasu polskiego (CET/CEST)
REM ================================================================
REM
REM  KONFIGURACJA EMAIL (wybierz jedną metodę):
REM
REM  Metoda 1: Zmienne środowiskowe
REM    set EMAIL_TO=twoj@email.com
REM    set EMAIL_FROM=twoj@email.com
REM    set EMAIL_PASSWORD=your_app_password
REM    set EMAIL_PROVIDER=gmail
REM
REM  Metoda 2: Plik email_config.py (skopiuj z email_config.example.py)
REM
REM  UWAGA: Aby scheduler działał 24/7:
REM    - Użyj Windows Task Scheduler (taskschd.msc)
REM    - Lub uruchom ten plik jako usługę (nssm install ...)
REM ================================================================

echo.
echo ================================================================
echo   MIDNIGHT SCHEDULER - Daily Email Notifications
echo ================================================================
echo.
echo   Scraper uruchamia sie codziennie o 02:00 (czas polski)
echo   Sporty: football, basketball, volleyball, handball,
echo           rugby, hockey, tennis
echo.

REM Sprawdź Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python nie znaleziony w PATH!
    pause
    exit /b 1
)

echo [OK] Python zainstalowany
echo.

REM Zainstaluj zależności
echo Instalowanie zaleznosci...
pip install -r requirements.txt >nul 2>&1
echo [OK] Zaleznosci zainstalowane
echo.

echo Uruchamiam scheduler... (Ctrl+C aby zatrzymac)
echo.

python midnight_scheduler.py

pause
