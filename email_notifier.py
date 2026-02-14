"""
Moduł do wysyłania powiadomień email o kwalifikujących się meczach
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict
import pandas as pd
from datetime import datetime
import math  # dla sprawdzania NaN

# Konfiguracja SMTP
SMTP_CONFIG = {
    'gmail': {
        'server': 'smtp.gmail.com',
        'port': 587,
        'use_tls': True
    },
    'outlook': {
        'server': 'smtp-mail.outlook.com',
        'port': 587,
        'use_tls': True
    },
    'yahoo': {
        'server': 'smtp.mail.yahoo.com',
        'port': 587,
        'use_tls': True
    }
}

def create_html_email(matches: List[Dict], date: str, sort_by: str = 'time') -> str:
    """
    Tworzy ładny HTML email z listą meczów
    
    Args:
        matches: Lista meczów
        date: Data
        sort_by: 'time' (godzina), 'wins' (liczba wygranych), 'team' (alfabetycznie)
    """
    
    # SORTOWANIE MECZÓW
    sorted_matches = matches.copy()
    
    if sort_by == 'time':
        # Sortuj po godzinie meczu
        def get_time_key(match):
            match_time = match.get('match_time', '')
            if not match_time:
                return '99:99'  # Mecze bez czasu na końcu
            
            # Wyciągnij godzinę z różnych formatów
            import re
            # Format: DD.MM.YYYY HH:MM lub HH:MM
            time_match = re.search(r'(\d{1,2}:\d{2})', match_time)
            if time_match:
                return time_match.group(1)
            return '99:99'
        
        sorted_matches = sorted(sorted_matches, key=get_time_key)
    
    elif sort_by == 'wins':
        # Sortuj po liczbie wygranych (malejąco) - uwzględnij tryb away_team_focus
        def get_wins(match):
            focus_team = match.get('focus_team', 'home')
            if focus_team == 'away':
                return match.get('away_wins_in_h2h_last5', 0)
            else:
                return match.get('home_wins_in_h2h_last5', 0)
        sorted_matches = sorted(sorted_matches, key=get_wins, reverse=True)
    
    elif sort_by == 'team':
        # Sortuj alfabetycznie po nazwie gospodarzy
        sorted_matches = sorted(sorted_matches, key=lambda x: x.get('home_team', '').lower())
    
    html = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .header {{
                background-color: #4CAF50;
                color: white;
                padding: 20px;
                text-align: center;
            }}
            .content {{
                padding: 20px;
            }}
            .match {{
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 15px;
                margin: 10px 0;
                background-color: #f9f9f9;
            }}
            .match-title {{
                font-size: 18px;
                font-weight: bold;
                color: #2196F3;
            }}
            .match-details {{
                margin: 5px 0;
                color: #666;
            }}
            .match-time {{
                font-size: 20px;
                color: #FF5722;
                font-weight: bold;
            }}
            .stats {{
                background-color: #fff3cd;
                padding: 10px;
                border-radius: 3px;
                margin-top: 10px;
            }}
            .footer {{
                text-align: center;
                padding: 20px;
                color: #888;
                font-size: 12px;
            }}
            .h2h-record {{
                color: #4CAF50;
                font-weight: bold;
            }}
            .time-badge {{
                display: inline-block;
                background-color: #FF5722;
                color: white;
                padding: 5px 10px;
                border-radius: 3px;
                margin-right: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🏆 Kwalifikujące się mecze - {date}</h1>
            <p>🎾 Tennis: Advanced scoring (≥50/100) | ⚽ Drużynowe: Gospodarze wygrali ≥60% H2H</p>
            <p style="font-size: 14px; margin-top: 10px;">⏰ Posortowane chronologicznie</p>
        </div>
        
        <div class="content">
            <p>Znaleziono <strong>{len(sorted_matches)}</strong> kwalifikujących się meczów:</p>
    """
    
    for i, match in enumerate(sorted_matches, 1):
        home = match.get('home_team', 'N/A')
        away = match.get('away_team', 'N/A')
        
        # Uwzględnij tryb away_team_focus
        focus_team = match.get('focus_team', 'home')
        if focus_team == 'away':
            wins = match.get('away_wins_in_h2h_last5', 0)
            focused_team_name = away
        else:
            wins = match.get('home_wins_in_h2h_last5', 0)
            focused_team_name = home
        
        match_time = match.get('match_time', 'Brak danych')
        match_url = match.get('match_url', '#')
        
        # Wyciągnij godzinę dla lepszego wyświetlania
        import re
        time_display = match_time
        time_badge = ''
        if match_time and match_time != 'Brak danych':
            time_match = re.search(r'(\d{1,2}:\d{2})', match_time)
            if time_match:
                time_only = time_match.group(1)
                time_badge = f'<span class="time-badge">🕐 {time_only}</span>'
                time_display = match_time
        
        # Sprawdź czy to tenis z advanced scoring (tylko tennis ma pole 'favorite')
        is_tennis = 'favorite' in match
        h2h_info = ''
        form_info = ''
        
        if is_tennis:  # Tennis z advanced scoring
            advanced_score = match.get('advanced_score', 0)
            
            # Wyświetl scoring dla tenisa
            favorite = match.get('favorite', 'unknown')
            if favorite == 'player_a':
                fav_name = home
            elif favorite == 'player_b':
                fav_name = away
            else:
                fav_name = "Równi"
            
            h2h_info = f'<span class="h2h-record">🎾 Score: {advanced_score:.1f}/100 | Faworytem: {fav_name}</span>'
        else:  # Sporty drużynowe (football, basketball, etc.)
            # H2H z win rate
            h2h_count = match.get('h2h_count', 0)
            win_rate = match.get('win_rate', 0.0)
            form_advantage = match.get('form_advantage', False)
            
            # Emoji dla przewagi formy
            advantage_emoji = ' 🔥' if form_advantage else ''
            
            if h2h_count > 0:
                # Dynamiczny komunikat w zależności od focus_team
                if focus_team == 'away':
                    h2h_info = f'<span class="h2h-record">📊 H2H: {away} (goście) wygrał {wins}/{h2h_count} ({win_rate*100:.0f}%){advantage_emoji}</span>'
                else:
                    h2h_info = f'<span class="h2h-record">📊 H2H: {home} wygrał {wins}/{h2h_count} ({win_rate*100:.0f}%){advantage_emoji}</span>'
            else:
                h2h_info = f'<span class="h2h-record">📊 H2H: Brak danych</span>'
            
            # ZAAWANSOWANA FORMA DRUŻYN (3 źródła)
            home_form_overall = match.get('home_form_overall', match.get('home_form', []))
            home_form_home = match.get('home_form_home', [])
            away_form_overall = match.get('away_form_overall', match.get('away_form', []))
            away_form_away = match.get('away_form_away', [])
            
            if home_form_overall or away_form_overall:
                # Funkcja pomocnicza do formatowania formy z emoji
                def format_form_with_emoji(form_list):
                    emoji_map = {'W': '✅', 'L': '❌', 'D': '🟡'}
                    return ' '.join([emoji_map.get(r, r) for r in form_list]) if form_list else 'N/A'
                
                # Formatuj formę
                home_overall_str = format_form_with_emoji(home_form_overall)
                home_home_str = format_form_with_emoji(home_form_home)
                away_overall_str = format_form_with_emoji(away_form_overall)
                away_away_str = format_form_with_emoji(away_form_away)
                
                # Oblicz przewagę
                home_wins = home_form_overall.count('W') if home_form_overall else 0
                away_wins = away_form_overall.count('W') if away_form_overall else 0
                
                form_info = f'''
                    <div style="margin-top: 10px; font-size: 13px; background-color: #F5F9FF; padding: 10px; border-radius: 5px;">
                        <strong>📊 Analiza Formy (ostatnie 5 meczów):</strong>
                        <div style="margin-top: 6px;">
                            <div style="margin-bottom: 4px;">
                                🏠 <strong>{home}:</strong>
                            </div>
                            <div style="margin-left: 20px; font-size: 12px;">
                                • Ogółem: <span style="background-color: #E8F5E9; padding: 2px 6px; border-radius: 3px;">{home_overall_str}</span>
                                {f'<br>• U siebie: <span style="background-color: #E8F5E9; padding: 2px 6px; border-radius: 3px;">{home_home_str}</span>' if home_form_home else ''}
                            </div>
                        </div>
                        <div style="margin-top: 8px;">
                            <div style="margin-bottom: 4px;">
                                ✈️ <strong>{away}:</strong>
                            </div>
                            <div style="margin-left: 20px; font-size: 12px;">
                                • Ogółem: <span style="background-color: #FFEBEE; padding: 2px 6px; border-radius: 3px;">{away_overall_str}</span>
                                {f'<br>• Na wyjeździe: <span style="background-color: #FFEBEE; padding: 2px 6px; border-radius: 3px;">{away_away_str}</span>' if away_form_away else ''}
                            </div>
                        </div>
                        {f'<div style="margin-top: 8px; padding: 6px; background-color: #FFF3CD; border-radius: 3px; font-weight: bold;">🔥 {focused_team_name} ma przewagę w formie!</div>' if form_advantage else ''}
                    </div>
                '''
        
        # NOWE: Informacja o ostatnim meczu H2H
        last_h2h_info = ''
        last_h2h_date = match.get('last_h2h_match_date')
        last_h2h_score = match.get('last_h2h_match_score')
        last_h2h_result = match.get('last_h2h_match_result')
        
        if last_h2h_date and last_h2h_score:
            result_emoji_map = {'W': '✅', 'L': '❌', 'D': '🟡', 'U': '❓'}
            result_emoji = result_emoji_map.get(str(last_h2h_result), '❓')
            result_text_map = {'W': 'Wygrana', 'L': 'Przegrana', 'D': 'Remis', 'U': 'Nieznany'}
            result_text = result_text_map.get(str(last_h2h_result), '')
            
            last_h2h_info = f'''
                <div style="margin-top: 8px; padding: 8px; background-color: #FFF8DC; border-left: 4px solid #FF8C00; border-radius: 3px; font-size: 13px;">
                    <strong>🕰️ Ostatni mecz H2H:</strong> {last_h2h_date} | Wynik: <strong>{last_h2h_score}</strong> {result_emoji} <em>({result_text})</em>
                </div>
            '''

        # Kursy bukmacherskie (jeśli dostępne)
        odds_html = ''
        home_odds = match.get('home_odds')
        away_odds = match.get('away_odds')
        
        # POPRAWKA: Sprawdź czy kursy są liczbami (nie NaN/None)
        # pandas NaN przechodzi przez `if home_odds and away_odds` i pokazuje się jako "nan"!
        has_valid_odds = False
        try:
            if home_odds is not None and away_odds is not None:
                # Sprawdź czy to liczby (nie NaN)
                if not (pd.isna(home_odds) or pd.isna(away_odds)):
                    # Dodatkowo sprawdź czy są w sensownym zakresie
                    if 1.0 <= float(home_odds) <= 100.0 and 1.0 <= float(away_odds) <= 100.0:
                        has_valid_odds = True
        except (ValueError, TypeError):
            pass
        
        if has_valid_odds:
            odds_html = f'''
                <div class="match-details" style="background-color: #FFF9E6; padding: 8px; border-radius: 5px; margin-top: 8px;">
                    🎲 <strong>Kursy:</strong> {home} <span style="background-color: #FFD700; padding: 2px 6px; border-radius: 3px; font-weight: bold;">{home_odds:.2f}</span> | {away} <span style="background-color: #FFD700; padding: 2px 6px; border-radius: 3px; font-weight: bold;">{away_odds:.2f}</span>
                    <br><em style="font-size: 11px; color: #666;">⚠️ Kursy są wyłącznie informacją dodatkową, nie wpływają na scoring</em>
                </div>
            '''
        
        html += f"""
            <div class="match">
                <div style="margin-bottom: 10px;">
                    {time_badge}
                </div>
                <div class="match-title">
                    #{i}. {home} vs {away}
                </div>
                <div class="match-details">
                    📅 Data: <strong>{time_display}</strong>
                </div>
                <div class="stats">
                    {h2h_info}
                    {last_h2h_info}
                    {form_info}
                </div>
                {odds_html}
                <div class="match-details">
                    🔗 <a href="{match_url}">Zobacz mecz na Livesport</a>
                </div>
            </div>
        """
    
    html += """
        </div>
        
        <div class="footer">
            <p>📧 Wygenerowano automatycznie przez Livesport H2H Scraper v6.1</p>
            <p>🔔 <strong>Kryteria kwalifikacji:</strong></p>
            <p>🎾 <strong>Tennis:</strong> Multi-factor scoring (H2H + ranking + forma + powierzchnia) ≥ 50/100</p>
            <p>⚽ <strong>Sporty drużynowe:</strong></p>
            <p style="margin-left: 20px;">
                1️⃣ Gospodarze wygrali ≥60% H2H<br>
                2️⃣ <strong>ZAAWANSOWANA ANALIZA FORMY (3 źródła):</strong><br>
                &nbsp;&nbsp;&nbsp;&nbsp;• Forma ogólna (ostatnie 5 meczów)<br>
                &nbsp;&nbsp;&nbsp;&nbsp;• Forma gospodarzy U SIEBIE<br>
                &nbsp;&nbsp;&nbsp;&nbsp;• Forma gości NA WYJEŹDZIE<br>
                3️⃣ Gospodarze w dobrej formie + Goście w słabej = 🔥 Przewaga!
            </p>
        </div>
    </body>
    </html>
    """
    
    return html


def create_over_under_html_email(matches: List[Dict], date: str, sport: str = 'football') -> str:
    """
    Tworzy specjalny HTML email z statystykami Over/Under
    
    Args:
        matches: Lista meczów z analizą O/U
        date: Data
        sport: Nazwa sportu
    """
    
    # Sortuj chronologicznie
    sorted_matches = matches.copy()
    def get_time_key(match):
        match_time = match.get('match_time', '')
        if not match_time:
            return '99:99'
        import re
        time_match = re.search(r'(\d{1,2}:\d{2})', match_time)
        if time_match:
            return time_match.group(1)
        return '99:99'
    sorted_matches = sorted(sorted_matches, key=get_time_key)
    
    # Emoji dla sportów
    sport_emoji = {
        'football': '⚽',
        'basketball': '🏀',
        'handball': '🤾',
        'volleyball': '🏐',
        'hockey': '🏒',
        'tennis': '🎾'
    }
    emoji = sport_emoji.get(sport, '📊')
    
    sport_name = sport.capitalize()
    
    html = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                text-align: center;
            }}
            .content {{
                padding: 20px;
            }}
            .match {{
                border: 2px solid #667eea;
                border-radius: 8px;
                padding: 15px;
                margin: 15px 0;
                background-color: #f9f9ff;
            }}
            .match-title {{
                font-size: 18px;
                font-weight: bold;
                color: #667eea;
                margin-bottom: 10px;
            }}
            .ou-section {{
                background-color: #fff;
                border-left: 4px solid #667eea;
                padding: 10px;
                margin: 10px 0;
            }}
            .ou-title {{
                font-size: 16px;
                font-weight: bold;
                color: #667eea;
                margin-bottom: 8px;
            }}
            .stat-row {{
                display: flex;
                justify-content: space-between;
                padding: 5px 0;
                border-bottom: 1px dotted #ddd;
            }}
            .stat-label {{
                color: #666;
            }}
            .stat-value {{
                font-weight: bold;
                color: #333;
            }}
            .odds-box {{
                background-color: #fff3cd;
                padding: 12px;
                border-radius: 5px;
                margin-top: 10px;
                border: 1px solid #ffc107;
            }}
            .odds-title {{
                font-weight: bold;
                color: #856404;
                margin-bottom: 8px;
            }}
            .odds-row {{
                display: flex;
                justify-content: space-around;
                margin-top: 8px;
            }}
            .odds-item {{
                text-align: center;
            }}
            .odds-label {{
                font-size: 12px;
                color: #666;
            }}
            .odds-value {{
                font-size: 20px;
                font-weight: bold;
                color: #28a745;
            }}
            .btts-section {{
                background-color: #e7f5ff;
                border-left: 4px solid #0366d6;
                padding: 10px;
                margin: 10px 0;
            }}
            .match-time {{
                font-size: 14px;
                color: #FF5722;
                font-weight: bold;
            }}
            .footer {{
                text-align: center;
                padding: 20px;
                color: #888;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{emoji} Over/Under Statistics - {sport_name}</h1>
            <h2>{date}</h2>
            <p style="font-size: 14px; margin-top: 10px;">
                💰 Mecze z wysokim prawdopodobieństwem Over/Under
            </p>
        </div>
        
        <div class="content">
            <p>Znaleziono <strong>{len(sorted_matches)}</strong> meczów z kwalifikującymi się statystykami O/U:</p>
    """
    
    for idx, match in enumerate(sorted_matches, 1):
        home_team = match.get('home_team', 'N/A')
        away_team = match.get('away_team', 'N/A')
        match_time = match.get('match_time', 'N/A')
        url = match.get('url', '#')
        
        ou_line = match.get('ou_line', 'N/A')
        ou_line_type = match.get('ou_line_type', 'goals')
        ou_h2h_pct = match.get('ou_h2h_percentage', 0)
        ou_recommendation = match.get('ou_recommendation', 'OVER')  # Domyślnie OVER
        
        over_odds = match.get('over_odds')
        under_odds = match.get('under_odds')
        
        btts_qualifies = match.get('btts_qualifies', False)
        btts_h2h_pct = match.get('btts_h2h_percentage', 0)
        btts_yes_odds = match.get('btts_yes_odds')
        btts_no_odds = match.get('btts_no_odds')
        
        # Tłumaczenie line_type
        line_type_pl = {
            'goals': 'bramek',
            'points': 'punktów',
            'sets': 'setów',
            'games': 'gemów'
        }.get(ou_line_type, ou_line_type)
        
        # Emoji dla rekomendacji
        rec_emoji = '⬆️' if ou_recommendation == 'OVER' else '⬇️'
        rec_text = f"{rec_emoji} {ou_recommendation}"
        
        html += f"""
            <div class="match">
                <div class="match-title">
                    #{idx}. {home_team} vs {away_team}
                </div>
                <div class="match-time">📅 {match_time}</div>
                <a href="{url}" style="font-size: 12px; color: #667eea;">🔗 Zobacz mecz na Livesport</a>
                
                <div class="ou-section">
                    <div class="ou-title">📊 Linia: {ou_line} {line_type_pl} | Rekomendacja: {rec_text}</div>
                    <div class="stat-row">
                        <span class="stat-label">🔥 H2H (ostatnie 5 meczów):</span>
                        <span class="stat-value">{ou_h2h_pct}% → {ou_recommendation}</span>
                    </div>
                </div>
        """
        
        # Kursy Over/Under
        if over_odds and under_odds:
            # Walidacja kursów (muszą być > 1.0 i < 100)
            import pandas as pd
            valid_over = not pd.isna(over_odds) and 1.0 < over_odds < 100
            valid_under = not pd.isna(under_odds) and 1.0 < under_odds < 100
            
            if valid_over and valid_under:
                # Podkreśl rekomendowany kurs
                over_style = 'font-weight: bold; color: #28a745; font-size: 24px;' if ou_recommendation == 'OVER' else 'color: #28a745; font-size: 20px;'
                under_style = 'font-weight: bold; color: #28a745; font-size: 24px;' if ou_recommendation == 'UNDER' else 'color: #28a745; font-size: 20px;'
                
                html += f"""
                <div class="odds-box">
                    <div class="odds-title">💰 KURSY (Nordic Bet):</div>
                    <div class="odds-row">
                        <div class="odds-item">
                            <div class="odds-label">Over {ou_line} {'⬆️' if ou_recommendation == 'OVER' else ''}</div>
                            <div class="odds-value" style="{over_style}">{over_odds}</div>
                        </div>
                        <div class="odds-item">
                            <div class="odds-label">Under {ou_line} {'⬇️' if ou_recommendation == 'UNDER' else ''}</div>
                            <div class="odds-value" style="{under_style}">{under_odds}</div>
                        </div>
                    </div>
                </div>
                """
        
        # BTTS (tylko dla football)
        if sport == 'football' and btts_qualifies:
            html += f"""
                <div class="btts-section">
                    <div class="ou-title">⚽ BTTS (Both Teams To Score)</div>
                    <div class="stat-row">
                        <span class="stat-label">🔥 H2H - obie drużyny strzeliły:</span>
                        <span class="stat-value">{btts_h2h_pct}%</span>
                    </div>
            """
            
            if btts_yes_odds and btts_no_odds:
                import pandas as pd
                valid_yes = not pd.isna(btts_yes_odds) and 1.0 < btts_yes_odds < 100
                valid_no = not pd.isna(btts_no_odds) and 1.0 < btts_no_odds < 100
                
                if valid_yes and valid_no:
                    html += f"""
                    <div class="odds-row" style="margin-top: 10px;">
                        <div class="odds-item">
                            <div class="odds-label">Yes</div>
                            <div class="odds-value">{btts_yes_odds}</div>
                        </div>
                        <div class="odds-item">
                            <div class="odds-label">No</div>
                            <div class="odds-value">{btts_no_odds}</div>
                        </div>
                    </div>
                    """
            
            html += "</div>"  # Zamknij btts-section
        
        html += "</div>"  # Zamknij match div
    
    html += """
        </div>
        
        <div class="footer">
            <p>📧 Automatyczne powiadomienie z volleyball-scraper</p>
            <p>💡 Statystyki bazują na analizie H2H i formy drużyn/zawodników</p>
            <p>⚠️ Zawsze sprawdzaj kursy przed obstawieniem!</p>
        </div>
    </body>
    </html>
    """
    
    return html


def send_email_notification(
    csv_file: str,
    to_email: str,
    from_email: str,
    password: str,
    provider: str = 'gmail',
    subject: str = None,
    sort_by: str = 'time',
    only_form_advantage: bool = False,
    skip_no_odds: bool = False,
    only_over_under: bool = False
):
    """
    Wysyła email z powiadomieniem o kwalifikujących się meczach
    
    Args:
        csv_file: Ścieżka do pliku CSV z wynikami
        to_email: Email odbiorcy
        from_email: Email nadawcy
        password: Hasło do email (lub App Password dla Gmail)
        provider: 'gmail', 'outlook', lub 'yahoo'
        subject: Opcjonalny tytuł emaila
        sort_by: Sortowanie: 'time' (godzina), 'wins' (wygrane), 'team' (alfabetycznie)
        only_form_advantage: Wysyłaj tylko mecze z przewagą formy gospodarzy (🔥)
        skip_no_odds: Pomijaj mecze bez kursów bukmacherskich
        only_over_under: Wysyłaj tylko mecze z kwalifikującymi się statystykami O/U (💰)
    """
    
    # Wczytaj dane
    print(f"Wczytuje dane z: {csv_file}")
    df = pd.read_csv(csv_file, encoding='utf-8')
    
    # OPCJA OVER/UNDER: Filtruj tylko mecze z O/U statistics
    if only_over_under:
        print("💰 TRYB: Tylko mecze z OVER/UNDER STATISTICS")
        if 'ou_qualifies' in df.columns:
            qualified = df[df['ou_qualifies'] == True]
            print(f"   Znaleziono {len(qualified)} meczów z kwalifikującymi się statystykami O/U")
        else:
            print("   ⚠️ Brak kolumny 'ou_qualifies' w danych")
            return
    else:
        # Standardowe filtrowanie po 'qualifies'
        qualified = df[df['qualifies'] == True]
    
    # OPCJA 1: Filtruj tylko mecze z przewagą formy (tylko dla standardowych meczów, nie O/U)
    if only_form_advantage and not only_over_under:
        print("🔥 TRYB: Tylko mecze z PRZEWAGĄ FORMY (gospodarzy/gości)")
        if 'form_advantage' in qualified.columns:
            qualified = qualified[qualified['form_advantage'] == True]
            print(f"   Przefiltrowano do meczów z przewagą formy")
        else:
            print("   ⚠️ Brak kolumny 'form_advantage' w danych - pokazuję wszystkie kwalifikujące")
    
    # OPCJA 2: Pomijaj mecze bez kursów
    if skip_no_odds:
        print("💰 TRYB: Pomijam mecze BEZ KURSÓW bukmacherskich")
        before_count = len(qualified)
        # Filtruj mecze, które mają OBA kursy (home_odds i away_odds)
        if 'home_odds' in qualified.columns and 'away_odds' in qualified.columns:
            qualified = qualified[(qualified['home_odds'].notna()) & (qualified['away_odds'].notna())]
            skipped = before_count - len(qualified)
            print(f"   Pominięto {skipped} meczów bez kursów")
        else:
            print("   ⚠️ Brak kolumn z kursami w danych - pokazuję wszystkie mecze")
    
    if len(qualified) == 0:
        messages = []
        if only_form_advantage:
            messages.append("PRZEWAGĄ FORMY")
        if skip_no_odds:
            messages.append("KURSAMI")
        
        print("="*70)
        print("⚠️  BRAK ZDARZEŃ DO WYSŁANIA")
        print("="*70)
        if messages:
            print(f"📊 Powód: Brak kwalifikujących się meczów z {' i '.join(messages)}")
        else:
            print(f"📊 Powód: Brak kwalifikujących się meczów")
        print(f"📄 CSV: {csv_file}")
        print(f"📧 Email: {to_email}")
        print("="*70)
        return

    # Policz mecze z kursami i bez (tylko jeśli nie pomijamy meczów bez kursów)
    if not skip_no_odds:
        with_odds = qualified[(qualified['home_odds'].notna()) & (qualified['away_odds'].notna())]
        without_odds = len(qualified) - len(with_odds)
    else:
        without_odds = 0  # Wszystkie mają kursy, bo filtrujemy

    # Komunikat o znalezionych meczach
    msg_parts = []
    if only_form_advantage:
        msg_parts.append("z PRZEWAGĄ FORMY 🔥")
    if skip_no_odds:
        msg_parts.append("z KURSAMI 💰")
    
    if msg_parts:
        print(f"Znaleziono {len(qualified)} kwalifikujacych sie meczow {' i '.join(msg_parts)}")
    else:
        print(f"Znaleziono {len(qualified)} kwalifikujacych sie meczow")
    
    if without_odds > 0 and not skip_no_odds:
        print(f"   W tym {without_odds} meczow bez kursow bukmacherskich")
    
    # Przygotuj dane
    matches = qualified.to_dict('records')
    date = datetime.now().strftime('%Y-%m-%d')
    
    if subject is None:
        if only_over_under:
            # Specjalny subject dla O/U
            subject = f"💰 OVER/UNDER Statistics - {len(qualified)} meczów - {date}"
        else:
            subject_parts = []
            if only_form_advantage:
                subject_parts.append("🔥 PRZEWAGA FORMY")
            if skip_no_odds:
                subject_parts.append("💰 Z KURSAMI")
            
            if subject_parts:
                subject = f"{len(qualified)} meczów ({' + '.join(subject_parts)}) - {date}"
            else:
                subject = f"{len(qualified)} kwalifikujacych sie meczow - {date}"
    
    # Utwórz wiadomość
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email
    
    # Dodaj treść HTML - wybierz odpowiedni template
    if only_over_under:
        # Wykryj sport z nazwy pliku CSV
        sport = 'football'  # domyślnie
        if 'basketball' in csv_file.lower() or 'koszykowka' in csv_file.lower():
            sport = 'basketball'
        elif 'volleyball' in csv_file.lower() or 'siatkowka' in csv_file.lower():
            sport = 'volleyball'
        elif 'handball' in csv_file.lower() or 'pilka-reczna' in csv_file.lower():
            sport = 'handball'
        elif 'hockey' in csv_file.lower() or 'hokej' in csv_file.lower():
            sport = 'hockey'
        elif 'tennis' in csv_file.lower() or 'tenis' in csv_file.lower():
            sport = 'tennis'
        
        html_content = create_over_under_html_email(matches, date, sport=sport)
    else:
        html_content = create_html_email(matches, date, sort_by=sort_by)
    
    html_part = MIMEText(html_content, 'html')
    msg.attach(html_part)
    
    # Wyślij email
    try:
        print(f"\nWysylam email do: {to_email}")
        print(f"   Provider: {provider}")
        
        smtp_config = SMTP_CONFIG[provider]
        
        with smtplib.SMTP(smtp_config['server'], smtp_config['port']) as server:
            if smtp_config['use_tls']:
                server.starttls()
            
            server.login(from_email, password)
            server.send_message(msg)
        
        print("Email wyslany pomyslnie!")
        
    except Exception as e:
        print(f"Blad wysylania emaila: {e}")
        print("\nWSKAZOWKI:")
        print("   - Dla Gmail: uzyj App Password (nie zwyklego hasla)")
        print("     Jak uzyskac: https://myaccount.google.com/apppasswords")
        print("   - Sprawdz czy SMTP jest wlaczony w ustawieniach konta")
        print("   - Sprawdz dane logowania")


def main():
    """Przykład użycia"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Wyślij powiadomienie email o kwalifikujących się meczach')
    parser.add_argument('--csv', required=True, help='Plik CSV z wynikami')
    parser.add_argument('--to', required=True, help='Email odbiorcy')
    parser.add_argument('--from-email', required=True, help='Email nadawcy')
    parser.add_argument('--password', required=True, help='Hasło email (lub App Password)')
    parser.add_argument('--provider', default='gmail', choices=['gmail', 'outlook', 'yahoo'], 
                       help='Provider email')
    parser.add_argument('--subject', help='Opcjonalny tytuł emaila')
    parser.add_argument('--sort', default='time', choices=['time', 'wins', 'team'],
                       help='Sortowanie: time (godzina), wins (wygrane), team (alfabetycznie)')
    parser.add_argument('--only-form-advantage', action='store_true',
                       help='🔥 Wyślij tylko mecze z PRZEWAGĄ FORMY gospodarzy')
    parser.add_argument('--skip-no-odds', action='store_true',
                       help='💰 Pomijaj mecze BEZ KURSÓW bukmacherskich')
    
    args = parser.parse_args()
    
    send_email_notification(
        csv_file=args.csv,
        to_email=args.to,
        from_email=args.from_email,
        password=args.password,
        provider=args.provider,
        subject=args.subject,
        sort_by=args.sort,
        only_form_advantage=args.only_form_advantage,
        skip_no_odds=args.skip_no_odds
    )


if __name__ == '__main__':
    main()

