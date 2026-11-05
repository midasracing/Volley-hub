# Test odczytu, 5 listopada 2026

Zwykłe żądania HTTP przez `requests`, bez przeglądarki i stealth, zwróciły HTTP 200
dla stron PZPS, stron pięciu grup II ligi w VolleyStation, listy drużyn II ligi
oraz terminarza, wyników, tabeli i 16 stron meczów Pomorskiej III ligi.

| Dane | II liga | Pomorska III liga |
| --- | ---: | ---: |
| Mecze | 532 | 72 |
| Zakończone mecze z wynikiem | 150 | 16 |
| Mecze z godziną | 532 | 72 |
| Drużyny z adresem logotypu | 54 | 9 |
| Wiersze tabel | 54, w 5 grupach | 9 |
| Mecze z punktami poszczególnych setów | 144 | 16 |

II liga: terminarze, wyniki i tabele pochodzą z VolleyStation. Godziny nadchodzących
meczów są w terminarzu VolleyStation; godziny zakończonych spotkań uzupełniono z PZPS
po dokładnym dopasowaniu grupy, daty i obu drużyn. Nie stosowano przybliżonego dopasowania
nazw. Wszystkie 54 nazwy drużyn z listy logotypów pasują po normalizacji do terminarza PZPS.

III liga: terminarz zawiera 56 nadchodzących meczów. Wyniki obejmują 16 zakończonych
spotkań; ich godziny i punkty setów odczytano z osobnych stron meczów.

Dla wszystkich pięciu grup II ligi i tabeli III ligi liczby rozegranych meczów,
zwycięstw i punktów zgadzają się z odczytanymi wynikami.

## Znalezione problemy

1. Produkcyjny parser tabel PZPS myli kolumny: dla Fortu Tarnowo Podgórne zapisuje
   `wins=10`, `points=287`, zamiast `wins=3`, `points=10`. Gubi też bilans setów.
   W kopii testowej pola są mapowane po nagłówkach; test regresji sprawdza ten przypadek.
2. Odczyt PZPS daje 144 wyniki, a VolleyStation 150: o jeden więcej w grupie 1
   i o pięć więcej w grupie 4. Dlatego eksport porównawczy używa wyników VolleyStation.
3. PZPS ma godziny tylko dla 197 z 532 spotkań. VolleyStation uzupełnia pozostałe
   godziny nadchodzących meczów; po połączeniu źródeł dostępne są wszystkie 532.
4. Logotypy są dostępne bez odwiedzania profili każdej drużyny. Trzeba obsługiwać
   również `badge.jpg` i `badge.jpeg`, nie tylko `badge.png`, oraz odróżniać logotyp
   drużyny od znaku całych rozgrywek.

To wynik jednego testu z tego środowiska. Cloudflare przepuścił żądania; na innym
adresie IP lub w innym terminie może zwrócić odmowę. Produkcyjne scrapery i feedy
pozostają bez zmian.
