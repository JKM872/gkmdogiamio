"""
LiveSport Odds API Client - pobieranie kursów bukmacherskich przez GraphQL API

Ten moduł łączy się z oficjalnym API Livesport aby pobrać kursy bukmacherskie.
Domyślnie używa Nordic Bet (ID: 165), ale można zmienić na innego bukmachera.

Źródło: Zintegrowane z livesportscraper repository
"""

import requests
import re
from typing import Dict, Optional, List
import time

# Sporty bez remisu - wymagają innego typu zakładu (HOME_AWAY zamiast HOME_DRAW_AWAY)
SPORTS_WITHOUT_DRAW = frozenset(['volleyball', 'basketball', 'handball', 'hockey', 'tennis'])

# Typy zakładów do próby dla sportów bez remisu (w kolejności priorytetów)
BET_TYPES_FOR_NO_DRAW_SPORTS = ['HOME_AWAY', 'MATCH_WINNER', 'HOME_DRAW_AWAY']

# Domyślny typ zakładu dla sportów z remisem (piłka nożna)
DEFAULT_BET_TYPE = 'HOME_DRAW_AWAY'


class LiveSportOddsAPI:
    """Klient do pobierania kursów bukmacherskich z LiveSport GraphQL API"""
    
    def __init__(self, bookmaker_id: str = "165", geo_ip_code: str = "PL", geo_subdivision: str = "PL10"):
        """
        Inicjalizuje klienta API (DOKŁADNIE JAK W LIVESPORTSCRAPER)
        
        Args:
            bookmaker_id: ID bukmachera (domyślnie "165" = Nordic Bet)
            geo_ip_code: Kod kraju (nie używany w obecnej wersji)
            geo_subdivision: Kod regionu (nie używany w obecnej wersji)
        """
        self.bookmaker_id = bookmaker_id
        self.geo_ip_code = geo_ip_code
        self.geo_subdivision = geo_subdivision
        
        # PRAWDZIWY Endpoint GraphQL API Livesport
        self.api_url = "https://global.ds.lsapp.eu/odds/pq_graphql"
        
        # Stwórz session (jak w livesportscraper)
        self.session = requests.Session()
        
        # Nagłówki HTTP (DOKŁADNIE JAK W LIVESPORTSCRAPER - linie 46-55)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'pl-PL,pl;q=0.9,en;q=0.8',
            'Origin': 'https://www.livesport.com',
            'Referer': 'https://www.livesport.com/',
            'sec-ch-ua': '"Google Chrome";v="141", "Not A(Brand";v="8", "Chromium";v="141"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        })
        
        # Mapowanie ID bukmacherów (najczęściej używane)
        self.bookmaker_names = {
            "165": "Nordic Bet",
            "16": "bet365",
            "8": "Unibet",
            "43": "William Hill",
            "14": "Bwin",
            "24": "Betfair",
        }
    
    
    def extract_event_id_from_url(self, url: str) -> Optional[str]:
        """
        Wydobywa Event ID z URL Livesport
        
        Args:
            url: URL meczu z Livesport (np. ".../?mid=ABC123")
        
        Returns:
            Event ID (np. "ABC123") lub None jeśli nie znaleziono
        
        Example:
            >>> url = "https://www.livesport.com/pl/mecz/pilka-nozna/team1/team2/?mid=KQAaF7d2"
            >>> extract_event_id_from_url(url)
            'KQAaF7d2'
        """
        # Szukaj parametru ?mid= lub &mid=
        match = re.search(r'[?&]mid=([a-zA-Z0-9]+)', url)
        if match:
            return match.group(1)
        
        # Alternatywnie: event ID może być w hash (#id/)
        match = re.search(r'#id/([a-zA-Z0-9]+)', url)
        if match:
            return match.group(1)
        
        return None
    
    
    def get_odds_for_event(self, event_id: str, sport: str = None) -> Optional[Dict]:
        """
        Pobiera kursy bukmacherskie dla konkretnego wydarzenia
        
        UŻYWA PRAWDZIWEGO ENDPOINTA LIVESPORT (odkrytego przez Selenium-Wire)
        
        Args:
            event_id: ID wydarzenia z Livesport (np. "KQAaF7d2")
            sport: Sport (np. 'football', 'volleyball', 'basketball') - używany do wyboru betType
        
        Returns:
            Słownik z kursami lub None
        """
        
        # Wybierz typy zakładów do próby w zależności od sportu
        # Dla sportów bez remisu (siatkówka, koszykówka, etc.) próbuj HOME_AWAY najpierw
        if sport and sport in SPORTS_WITHOUT_DRAW:
            bet_types_to_try = BET_TYPES_FOR_NO_DRAW_SPORTS
        else:
            bet_types_to_try = [DEFAULT_BET_TYPE]
        
        # Próbuj każdy typ zakładu po kolei, aż znajdziemy kursy
        for bet_type in bet_types_to_try:
            result = self._fetch_odds_with_bet_type(event_id, bet_type)
            if result:
                return result
        
        return None
    
    def _fetch_odds_with_bet_type(self, event_id: str, bet_type: str) -> Optional[Dict]:
        """
        Wewnętrzna metoda do pobierania kursów z konkretnym typem zakładu
        
        Args:
            event_id: ID wydarzenia z Livesport
            bet_type: Typ zakładu (np. 'HOME_DRAW_AWAY', 'HOME_AWAY', 'MATCH_WINNER')
        
        Returns:
            Słownik z kursami lub None
        """
        try:
            # PRAWDZIWE parametry (DOKŁADNIE JAK W LIVESPORTSCRAPER - linie 149-155)
            params = {
                '_hash': 'ope2',  # Hash dla kursów ("odds per bookmaker")
                'eventId': event_id,
                'bookmakerId': self.bookmaker_id,  # 165 = Nordic Bet
                'betType': bet_type,  # Typ zakładu: zależny od sportu
                'betScope': 'FULL_TIME'  # Pełen czas (nie połowy)
            }
            
            # GET request do prawdziwego API (UŻYWAMY SESSION - linia 161)
            response = self.session.get(
                self.api_url,
                params=params,
                timeout=10
            )
            
            # Sprawdź status - nie wyświetlaj błędów dla każdego betType (może być normalne)
            if response.status_code != 200:
                return None
            
            response.raise_for_status()
            data = response.json()
            
            # Parsuj odpowiedź (DOKŁADNIE JAK W LIVESPORTSCRAPER - linie 176-192)
            if 'data' in data and 'findPrematchOddsForBookmaker' in data['data']:
                odds_data = data['data']['findPrematchOddsForBookmaker']
                
                # Sprawdź czy odds_data nie jest None/puste
                if not odds_data:
                    return None
                
                result = {
                    'bookmaker_id': self.bookmaker_id,
                    'bookmaker_name': self.bookmaker_names.get(self.bookmaker_id, 'Nordic Bet'),
                    'source': 'livesport_api',
                    'event_id': event_id,
                    'bet_type_used': bet_type  # Dodatkowa informacja o użytym typie
                }
                
                # HOME odds - próbuj różne klucze (home, team1, 1)
                home_value = None
                for key in ['home', 'team1', '1']:
                    if key in odds_data and odds_data[key]:
                        home_value = odds_data[key].get('value')
                        if home_value:
                            result['home_odds'] = float(home_value)
                            break
                
                # DRAW odds (może nie istnieć dla niektórych sportów)
                if 'draw' in odds_data and odds_data['draw']:
                    draw_value = odds_data['draw'].get('value')
                    if draw_value:
                        result['draw_odds'] = float(draw_value)
                
                # AWAY odds - próbuj różne klucze (away, team2, 2)
                away_value = None
                for key in ['away', 'team2', '2']:
                    if key in odds_data and odds_data[key]:
                        away_value = odds_data[key].get('value')
                        if away_value:
                            result['away_odds'] = float(away_value)
                            break
                
                # Sprawdź czy mamy przynajmniej home i away
                if result.get('home_odds') and result.get('away_odds'):
                    return result
            
            return None
        
        except requests.exceptions.RequestException as e:
            # Cichy błąd - nie spamuj logów przy próbach różnych betType
            return None
        
        except (KeyError, ValueError, TypeError) as e:
            return None
    
    
    def get_odds_from_url(self, match_url: str, sport: str = None) -> Optional[Dict]:
        """
        Pobiera kursy bukmacherskie bezpośrednio z URL meczu
        
        Args:
            match_url: Pełny URL meczu z Livesport
            sport: Sport (opcjonalnie) - jeśli nie podany, próbuje wykryć z URL
        
        Returns:
            Słownik z kursami (jak get_odds_for_event) lub None
        
        Example:
            >>> client = LiveSportOddsAPI()
            >>> url = "https://www.livesport.com/pl/mecz/pilka-nozna/team1/team2/?mid=ABC123"
            >>> odds = client.get_odds_from_url(url)
            >>> print(f"Home: {odds['home_odds']}, Away: {odds['away_odds']}")
        """
        # Wydobądź Event ID z URL
        event_id = self.extract_event_id_from_url(match_url)
        
        if not event_id:
            print(f"   ⚠️ Nie znaleziono Event ID w URL: {match_url}")
            return None
        
        # Jeśli sport nie podany, spróbuj wykryć z URL
        if not sport:
            sport = self._detect_sport_from_url(match_url)
        
        # Pobierz kursy dla tego event
        return self.get_odds_for_event(event_id, sport=sport)
    
    def _detect_sport_from_url(self, url: str) -> str:
        """
        Wykrywa sport z URL Livesport
        
        Args:
            url: URL meczu
        
        Returns:
            Nazwa sportu (np. 'football', 'volleyball') lub 'football' jako domyślny
        """
        url_lower = url.lower()
        
        # Mapowanie fragmentów URL na sporty
        sport_patterns = {
            'siatkowka': 'volleyball',
            'volleyball': 'volleyball',
            'koszykowka': 'basketball',
            'basketball': 'basketball',
            'pilka-reczna': 'handball',
            'handball': 'handball',
            'hokej': 'hockey',
            'hockey': 'hockey',
            'tenis': 'tennis',
            'tennis': 'tennis',
            'pilka-nozna': 'football',
            'football': 'football',
            'soccer': 'football',
        }
        
        for pattern, sport in sport_patterns.items():
            if pattern in url_lower:
                return sport
        
        # Domyślnie football
        return 'football'
    
    
    def get_over_under_odds(self, event_id: str, sport: str = 'football') -> Optional[Dict]:
        """
        Pobiera kursy Over/Under dla wydarzenia
        
        Args:
            event_id: ID wydarzenia z Livesport
            sport: Sport ('football', 'basketball', 'handball', 'volleyball', 'hockey', 'tennis')
        
        Returns:
            Słownik z kursami O/U:
            {
                'over_2_5': 1.85,
                'under_2_5': 1.95,
                'btts_yes': 1.75,  # tylko football
                'btts_no': 2.05,   # tylko football
                'line': '2.5',
                'line_type': 'goals'
            }
        """
        try:
            # Parametry dla Over/Under
            params = {
                '_hash': 'ope2',
                'eventId': event_id,
                'bookmakerId': self.bookmaker_id,
                'betType': 'OVER_UNDER',  # Typ zakładu O/U
                'betScope': 'FULL_TIME'
            }
            
            # GET request
            response = self.session.get(
                self.api_url,
                params=params,
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"   ⚠️ API O/U ERROR {response.status_code}: {response.text[:200]}")
                return None
            
            response.raise_for_status()
            data = response.json()
            
            # Parsuj odpowiedź
            if 'data' in data and 'findPrematchOddsForBookmaker' in data['data']:
                odds_data = data['data']['findPrematchOddsForBookmaker']
                
                result = {
                    'bookmaker_id': self.bookmaker_id,
                    'bookmaker_name': self.bookmaker_names.get(self.bookmaker_id, 'Nordic Bet'),
                    'source': 'livesport_api',
                    'event_id': event_id
                }
                
                # OVER odds
                if 'over' in odds_data and odds_data['over']:
                    over_value = odds_data['over'].get('value')
                    line = odds_data['over'].get('line', '2.5')  # Linia O/U
                    if over_value:
                        result['over_odds'] = float(over_value)
                        result['line'] = str(line)
                
                # UNDER odds
                if 'under' in odds_data and odds_data['under']:
                    under_value = odds_data['under'].get('value')
                    if under_value:
                        result['under_odds'] = float(under_value)
                
                # Typ linii zależy od sportu
                if sport == 'football':
                    result['line_type'] = 'goals'
                elif sport in ['basketball', 'volleyball']:
                    result['line_type'] = 'points'
                elif sport in ['handball', 'hockey']:
                    result['line_type'] = 'goals'
                elif sport == 'tennis':
                    result['line_type'] = 'sets'
                
                # Sprawdź czy mamy kursy
                if result.get('over_odds') and result.get('under_odds'):
                    return result
            
            return None
        
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️ Błąd API O/U request: {e}")
            return None
        
        except (KeyError, ValueError, TypeError) as e:
            print(f"   ⚠️ Błąd parsowania O/U: {e}")
            return None
    
    
    def get_btts_odds(self, event_id: str) -> Optional[Dict]:
        """
        Pobiera kursy BTTS (Both Teams To Score) dla piłki nożnej
        
        Returns:
            {
                'btts_yes': 1.75,
                'btts_no': 2.05
            }
        """
        try:
            params = {
                '_hash': 'ope2',
                'eventId': event_id,
                'bookmakerId': self.bookmaker_id,
                'betType': 'BOTH_TEAMS_SCORE',
                'betScope': 'FULL_TIME'
            }
            
            response = self.session.get(
                self.api_url,
                params=params,
                timeout=10
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            if 'data' in data and 'findPrematchOddsForBookmaker' in data['data']:
                odds_data = data['data']['findPrematchOddsForBookmaker']
                
                result = {}
                
                # YES (obie drużyny strzelą)
                if 'yes' in odds_data and odds_data['yes']:
                    yes_value = odds_data['yes'].get('value')
                    if yes_value:
                        result['btts_yes'] = float(yes_value)
                
                # NO (przynajmniej jedna drużyna nie strzeli)
                if 'no' in odds_data and odds_data['no']:
                    no_value = odds_data['no'].get('value')
                    if no_value:
                        result['btts_no'] = float(no_value)
                
                if result.get('btts_yes') and result.get('btts_no'):
                    return result
            
            return None
        
        except Exception as e:
            print(f"   ⚠️ Błąd BTTS: {e}")
            return None
    
    
    def get_complete_odds(self, event_id: str, sport: str = 'football') -> Dict:
        """
        Pobiera WSZYSTKIE kursy dla wydarzenia (1X2 + O/U + BTTS)
        
        Args:
            event_id: ID wydarzenia z Livesport
            sport: Sport (np. 'football', 'volleyball') - wpływa na wybór betType
        
        Returns:
            {
                # 1X2 (lub 1/2 dla sportów bez remisu)
                'home_odds': 1.85,
                'draw_odds': 3.50,  # None dla sportów bez remisu
                'away_odds': 4.20,
                
                # Over/Under
                'over_odds': 1.85,
                'under_odds': 1.95,
                'ou_line': '2.5',
                
                # BTTS (tylko football)
                'btts_yes': 1.75,
                'btts_no': 2.05
            }
        """
        result = {}
        
        # 1. Pobierz kursy 1X2 (lub 1/2 dla sportów bez remisu)
        main_odds = self.get_odds_for_event(event_id, sport=sport)
        if main_odds:
            result.update(main_odds)
        
        # 2. Pobierz kursy O/U
        ou_odds = self.get_over_under_odds(event_id, sport)
        if ou_odds:
            result['over_odds'] = ou_odds.get('over_odds')
            result['under_odds'] = ou_odds.get('under_odds')
            result['ou_line'] = ou_odds.get('line', '2.5')
            result['ou_line_type'] = ou_odds.get('line_type', 'goals')
        
        # 3. Pobierz kursy BTTS (tylko dla football)
        if sport == 'football':
            btts_odds = self.get_btts_odds(event_id)
            if btts_odds:
                result['btts_yes'] = btts_odds.get('btts_yes')
                result['btts_no'] = btts_odds.get('btts_no')
        
        return result


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_odds_for_matches_batch(match_urls: list, bookmaker_id: str = "165", 
                                delay: float = 0.5, verbose: bool = True) -> list:
    """
    Pobiera kursy dla listy URL-i meczów (batch processing)
    
    Args:
        match_urls: Lista URL-i meczów
        bookmaker_id: ID bukmachera (domyślnie "165" = Nordic Bet)
        delay: Opóźnienie między requestami (w sekundach)
        verbose: Czy wyświetlać logi
    
    Returns:
        Lista słowników z danymi meczów + kursami
    """
    if verbose:
        print(f"🎲 Rozpoczynam pobieranie kursów dla {len(match_urls)} meczów...")
        print(f"📊 Bukmacher: {bookmaker_id}")
    
    client = LiveSportOddsAPI(bookmaker_id=bookmaker_id)
    results = []
    
    for i, url in enumerate(match_urls, 1):
        if verbose:
            print(f"\n[{i}/{len(match_urls)}] {url}")
        
        odds = client.get_odds_from_url(url)
        
        if odds:
            result = {
                'match_url': url,
                'home_odds': odds['home_odds'],
                'draw_odds': odds['draw_odds'],
                'away_odds': odds['away_odds'],
                'bookmaker_name': odds['bookmaker_name'],
                'source': odds['source']
            }
            results.append(result)
            
            if verbose:
                print(f"   ✅ Home: {odds['home_odds']}, ", end='')
                if odds['draw_odds']:
                    print(f"Draw: {odds['draw_odds']}, ", end='')
                print(f"Away: {odds['away_odds']}")
        else:
            if verbose:
                print(f"   ⚠️ Brak kursów")
        
        # Rate limiting - nie spamuj API
        if i < len(match_urls):
            time.sleep(delay)
    
    if verbose:
        print(f"\n{'='*70}")
        print(f"✅ Pobrano kursy dla {len(results)}/{len(match_urls)} meczów")
    
    return results


# ============================================================================
# PRZYKŁAD UŻYCIA
# ============================================================================

if __name__ == "__main__":
    print("="*70)
    print("🎲 LIVESPORT ODDS API CLIENT - TEST")
    print("="*70)
    
    # Test 1: Pojedynczy mecz
    print("\n📝 TEST 1: Pobieranie kursów dla pojedynczego meczu")
    
    client = LiveSportOddsAPI(bookmaker_id="165")  # Nordic Bet
    
    # Przykładowy URL (ZMIEŃ NA AKTUALNY MECZ!)
    test_url = "https://www.livesport.com/pl/mecz/pilka-nozna/atalanta-8C9JjMXu/slavia-praga-viXGgnyB/?mid=KQAaF7d2"
    
    print(f"URL: {test_url}")
    
    odds = client.get_odds_from_url(test_url)
    
    if odds:
        print(f"\n✅ Kursy pobrane pomyślnie:")
        print(f"   🏠 Gospodarz: {odds['home_odds']}")
        if odds['draw_odds']:
            print(f"   ⚖️  Remis: {odds['draw_odds']}")
        print(f"   ✈️  Gość: {odds['away_odds']}")
        print(f"   📊 Źródło: {odds['bookmaker_name']}")
        print(f"   🔗 API: {odds['source']}")
    else:
        print("\n❌ Nie udało się pobrać kursów")
        print("   Możliwe przyczyny:")
        print("   - URL nie zawiera parametru ?mid=")
        print("   - Mecz nie ma dostępnych kursów w Nordic Bet")
        print("   - Event ID jest nieprawidłowe")
    
    # Test 2: Batch processing
    print("\n" + "="*70)
    print("📝 TEST 2: Batch processing (wiele meczów)")
    
    test_urls = [
        test_url,
        # Dodaj więcej URL-i do testu...
    ]
    
    results = get_odds_for_matches_batch(
        match_urls=test_urls,
        bookmaker_id="165",
        delay=0.5,
        verbose=True
    )
    
    print(f"\n✨ Gotowe! Pobrano kursy dla {len(results)} meczów.")

