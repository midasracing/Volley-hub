# Publiczny endpoint PZPS — wynik sprawdzenia

Sprawdzono 5 listopada 2026 r.:

```text
GET https://sedziowie.pzps.pl/system/webapi.php
```

HTTP 200, JSON UTF-8, bez tokena i logowania. Odpowiedź zawiera 6 kategorii
rozgrywek; dla II ligi mężczyzn ma 26 rekordów wyników. To mniej niż 150 wyników
odczytanych tego dnia z VolleyStation. Nie jest to potwierdzony pełny terminarz.

## Parametry

Wszystkie poniższe zapytania zwróciły identyczny JSON jak adres bez parametrów:

```text
?version
?score
?clubs
?table
?type=9
?version=1
?clubs=1
?table&gender=2&age=4&class=2&phase=1&group=1
```

Porównano sumy SHA-256 JSON po normalizacji. W tym teście parametry nie zmieniały
zwracanych danych. Sam status 200 dla `?table` lub `?clubs` nie potwierdza obsługi
tabel ani listy klubów. Nie potwierdzono innych działających filtrów tego endpointu.

Znaleziono oficjalną [dokumentację API SZPS](https://system.szps.pl/sedzia/32/API_DOCUMENTATION.pdf).
Opisuje m.in. odczyt wyników, klubów i tabel, ale dotyczy domeny `system.szps.pl`.
Nie należy traktować jej jako dokumentacji instalacji PZPS: odpowiedzi PZPS
nie mają opisanego tam pola wersji i w testach nie reagują na powyższe parametry.

## Struktura i odczyt II ligi mężczyzn

Odpowiedź jest tablicą zagnieżdżonych par: nazwa rozgrywek → faza → grupa → wyniki.
Wiersz wyniku zawiera gospodarza, gościa i wynik zapisany jako tekst HTML.

```python
import requests
from bs4 import BeautifulSoup

response = requests.get("https://sedziowie.pzps.pl/system/webapi.php", timeout=20)
response.raise_for_status()
for competition, phases in response.json():
    if competition.strip() != "II Liga Mężczyzn":
        continue
    for phase, groups in phases:
        for group, matches in groups:
            for home, away, score_html in matches:
                score = BeautifulSoup(score_html, "html.parser").get_text(" ", strip=True)
                print(group, home.strip(), away.strip(), score)
```

Sprawdzona odpowiedź nie zawiera dat, godzin, ID meczów, logotypów ani tabel ligowych.
Brak ID i dat utrudnia jednoznaczne połączenie wyniku z konkretnym spotkaniem
w sezonie. Nie potwierdzono aktualizacji punkt po punkcie ani częstotliwości odświeżania.

## Powtórzenie testu

```bash
python diagnostics/probe_pzps_api.py
python diagnostics/probe_pzps_api.py --offline
```

Odpowiedzi, metadane i porównanie sum są zapisywane w
`diagnostics/artifacts/pzps-api/`. Skrypt wykonuje wyłącznie odczyty GET.
