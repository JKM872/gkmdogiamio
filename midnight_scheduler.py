"""
SCHEDULER: Automatyczne uruchomienie scrapingu o 02:00 czasu polskiego
======================================================================

Uruchomienie lokalne:  python midnight_scheduler.py
Na GitHub Actions:     Workflow midnight-auto-scraping.yml (cron)

Funkcjonalność:
- Uruchamia scraping codziennie o 02:00 (CET/CEST - czas polski)
- Scrapuje WSZYSTKIE wspierane sporty
- Wysyła powiadomienia email automatycznie
- Obsługa stref czasowych (CET zimą / CEST latem)
- Pełne logowanie do pliku i konsoli
"""

import schedule
import time
import logging
import os
import sys
import traceback
from datetime import datetime

try:
    import pytz
    TZ = pytz.timezone('Europe/Warsaw')
except ImportError:
    print("⚠️  Brak modułu pytz - instaluję...")
    os.system(f'{sys.executable} -m pip install pytz')
    import pytz
    TZ = pytz.timezone('Europe/Warsaw')

# Import modułu scrapingu
from scrape_and_notify import scrape_and_send_email

# ============================================================================
# KONFIGURACJA
# ============================================================================

# Utwórz folder na logi
os.makedirs('logs', exist_ok=True)

# Logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/midnight_scheduler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Email - kolejność priorytetu:
# 1. Zmienne środowiskowe (EMAIL_TO, EMAIL_FROM, EMAIL_PASSWORD, EMAIL_PROVIDER)
# 2. Plik email_config.py (TO_EMAIL, FROM_EMAIL, PASSWORD, PROVIDER)
TO_EMAIL = os.environ.get('EMAIL_TO')
FROM_EMAIL = os.environ.get('EMAIL_FROM')
PASSWORD = os.environ.get('EMAIL_PASSWORD')
PROVIDER = os.environ.get('EMAIL_PROVIDER', 'gmail')

if not all([TO_EMAIL, FROM_EMAIL, PASSWORD]):
    try:
        from email_config import TO_EMAIL, FROM_EMAIL, PASSWORD, PROVIDER
        logger.info("📧 Załadowano konfigurację email z email_config.py")
    except ImportError:
        logger.warning("⚠️  Brak konfiguracji email!")
        logger.warning("   Ustaw zmienne: EMAIL_TO, EMAIL_FROM, EMAIL_PASSWORD")
        logger.warning("   LUB stwórz plik email_config.py (wzór: email_config.example.py)")
else:
    logger.info("📧 Załadowano konfigurację email ze zmiennych środowiskowych")

# Wszystkie sporty
ALL_SPORTS = ['football', 'basketball', 'volleyball', 'handball', 'rugby', 'hockey', 'tennis']

# Godzina uruchomienia (02:00 czasu polskiego)
SCHEDULED_HOUR = 2
SCHEDULED_MINUTE = 0


# ============================================================================
# FUNKCJE
# ============================================================================

def get_polish_time():
    """Aktualny czas w strefie Europe/Warsaw"""
    return datetime.now(TZ)


def get_today_date():
    """Dzisiejsza data (czas polski) w formacie YYYY-MM-DD"""
    return get_polish_time().strftime('%Y-%m-%d')


def run_midnight_scraper():
    """Główna funkcja scrapingu - uruchamiana o 02:00"""

    logger.info("=" * 70)
    logger.info("🌙 MIDNIGHT SCRAPER - START")
    logger.info("=" * 70)

    current_time = get_polish_time()
    today_date = get_today_date()

    logger.info(f"⏰ Czas polski: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info(f"📅 Data: {today_date}")
    logger.info(f"⚽ Sporty: {', '.join(ALL_SPORTS)}")

    if not all([TO_EMAIL, FROM_EMAIL, PASSWORD]):
        logger.error("❌ BRAK konfiguracji email - nie można wysłać powiadomień!")
        logger.error("   Ustaw EMAIL_TO, EMAIL_FROM, EMAIL_PASSWORD")
        return

    logger.info(f"📧 Email do: {TO_EMAIL}")
    logger.info(f"🔧 Provider: {PROVIDER}")

    try:
        scrape_and_send_email(
            date=today_date,
            sports=ALL_SPORTS,
            to_email=TO_EMAIL,
            from_email=FROM_EMAIL,
            password=PASSWORD,
            provider=PROVIDER,
            headless=True,
            max_matches=None,
            sort_by='time',
            only_form_advantage=False,
            skip_no_odds=False,
            only_over_under=False,
            away_team_focus=False
        )
        logger.info("✅ Scraping zakończony pomyślnie!")

    except Exception as e:
        logger.error(f"❌ Błąd podczas scrapingu: {e}")
        logger.error(traceback.format_exc())

    logger.info("=" * 70)


def main():
    """Główna pętla schedulera (tryb lokalny / daemon)"""

    logger.info("")
    logger.info("=" * 70)
    logger.info("🌙 MIDNIGHT SCHEDULER")
    logger.info(f"   Czas systemowy:  {datetime.now()}")
    logger.info(f"   Czas polski:     {get_polish_time()}")
    logger.info(f"   Zaplanowany na:  {SCHEDULED_HOUR:02d}:{SCHEDULED_MINUTE:02d} (CET/CEST)")
    logger.info(f"   Sporty:          {', '.join(ALL_SPORTS)}")
    logger.info("=" * 70)

    # Zaplanuj codziennie o SCHEDULED_HOUR:SCHEDULED_MINUTE
    schedule.every().day.at(f"{SCHEDULED_HOUR:02d}:{SCHEDULED_MINUTE:02d}").do(run_midnight_scraper)

    logger.info("✅ Scheduler gotowy. Czekam na 02:00...")
    logger.info("💡 Aby zakończyć: Ctrl+C")
    logger.info("")

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)  # Sprawdzaj co 30 sekund
    except KeyboardInterrupt:
        logger.info("\n🛑 Scheduler zatrzymany przez użytkownika.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Krytyczny błąd: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()
