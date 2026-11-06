# Audyt II ligi i Pomorskiej III ligi (6 listopada 2026)

Porównanie zapisanych danych `data/2liga.json`, `data/pomorska3liga.json`
i pól `data/tauron.json` z użyciem
[`scripts/audit_lower_leagues.py`](../scripts/audit_lower_leagues.py).
Audyt jest bez sieci i nie zmienia wyników źródłowych.

| Metryka | II Liga Mężczyzn | Pomorska III Liga Męska |
| --- | ---: | ---: |
| Grupy | 5 | 1 liga regionalna |
| Drużyny | 54 | 9 |
| Logotypy | 54/54 | 9/9 |
| Mecze | 532 | 72 |
| Zakończone | 145 | 15 |
| Zakończone z punktami każdego seta | 145/145 | 14/15 |
| Z godziną rozpoczęcia | 197/532 | 71/72 |
| Wiersze tabeli | 54/54 | 9/9 |
| Format TAURON — komplet bazowych pól | nie | nie |

## Znalezione i naprawione

- 6 listopada poprawiono produkcyjny parser tabel II ligi. Poprzednio heurystyka
  liczbowa interpretowała punkty meczowe jako punkty bilansu i myliła zwycięstwa:
  np. Fort Tarnowo Podgórne miał `wins=10` i `points=287` zamiast
  `wins=3` i `points=10`. Teraz używamy **dokładnych nazw kolumn PZPS**.
  Poprawny odczyt potwierdził test regresji i udane uruchomienie aktualizatora.
- W grupach II ligi **1, 2, 3 i 5** tabele zgadzają się ze znanymi wynikami.
  W **grupie 4** pozostaje 6 rozbieżnych wierszy: oficjalna tabela uwzględnia
  wyniki, których nie ma jeszcze w zebranym feedzie (m.in. pięć spotkań znanych
  z porównania VolleyStation). Dane nie zostały sfałszowane, aby ukryć różnicę.

## Pozostałe braki i przyczyny

1. **II liga:** 335 spotkań nie ma godziny rozpoczęcia w PZPS. Historyczny
   test VolleyStation znalazł wszystkie 532 godziny, ale runner GitHub Actions
   dostał HTTP 403 od Cloudflare; automatyczne uzupełnienie nie działa
   z jego sieci. Harmonogram i punktacja setów są zachowane.
2. **Pomorska III liga:** źródło VolleyStation blokuje aktualizator na runnerze
   GitHuba (HTTP 403), również z włączonym Puppeteer Stealth. Ostatnia
   zapisana aktualizacja danych pochodzi z **4 listopada**. O jeden mecz
   i jeden kompletny wynik setów jest mniej niż w teście z 5 listopada.
3. Pomorska III Liga to **tylko region pomorski**. Projekt nie agreguje
   wszystkich regionalnych lig III szczebla.
4. Oba feedy mają starszą strukturę niż TAURON Liga: II nie ma stabilnych
   ID meczów, `source_url` dla poszczególnych spotkań, `date_iso`,
   `set_points`, `home_points`, `away_points` itd. Pomorska III ma
   `id` i `source_url`, ale również brakuje innych pól.

## Bezpieczne działania

- Codzienny workflow
  [`audit-lower-leagues.yml`](../.github/workflows/audit-lower-leagues.yml)
  generuje `lower-leagues-audit.json` z rozbieżnościami grup, wyników
  i schematu, bez nadpisywania rekordów.
- Przed aktualizacją II ligi działa regresja tabel PZPS.
- Kolejny etap to uzupełnienie schematu TAURON polami pochodnymi, a przede
  wszystkim przywrócenie dostępu do aktualnych danych Pomorskiej III ligi
  z dozwolonego i działającego źródła. **Nie należy obchodzić ograniczeń
  dostępu ani dopisywać brakujących wyników na podstawie tabeli.**
