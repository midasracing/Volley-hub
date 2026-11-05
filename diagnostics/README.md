# Diagnostyka II i Pomorskiej III ligi

Kopie scraperów są w `scrapers/`. Pochodzenie i sumy SHA-256 oryginałów zapisano w
`sources.json`. Produkcyjne `scripts/update_2liga.py`, `scripts/update_pomorska3liga.py`
i pliki `data/*.json` nie są zmieniane przez te testy.

W kopiach zmieniono katalog zapisu na `diagnostics/artifacts/standalone/` oraz
pobieranie stron na zwykły HTTP przez `requests`. Kopia II ligi dodatkowo poprawia
mapowanie kolumn tabeli PZPS. Kopia III ligi pozwala wyłączyć kontrolę liczby 9 drużyn,
gdy jej parser tabel jest używany do testowania grup II ligi.

## Uruchomienie

Z głównego katalogu repozytorium, z Pythonem 3.10+:

```bash
python3 -m venv .venv-diagnostics
source .venv-diagnostics/bin/activate
python -m pip install -r diagnostics/requirements.txt

# PZPS: terminarz, wyniki i tabele II ligi; VolleyStation: loga II ligi
# oraz terminarz, wyniki, tabele, loga i godziny Pomorskiej III ligi
python diagnostics/probe_leagues.py

# VolleyStation: wszystkie pięć grup II ligi; uzupełnienie godzin z PZPS
python diagnostics/probe_2liga_volleystation.py

# Porównanie publicznych zapytań do webapi.php PZPS
python diagnostics/probe_pzps_api.py

# Ponowne parsowanie zapisanych stron, bez żądań sieciowych
python diagnostics/probe_leagues.py --offline
python diagnostics/probe_2liga_volleystation.py --offline

python -m unittest discover -s diagnostics/tests -v
```

Najpierw uruchom `probe_leagues.py`: drugi skrypt korzysta z zapisanej listy drużyn
i danych PZPS. Opcja `--output KATALOG` zmienia katalog artefaktów; przy obu poleceniach
należy podać ten sam katalog.

## Artefakty

Domyślnie w `diagnostics/artifacts/probe/` powstają:

- `*.html` oraz `*.http.json`: pobrana strona i jej URL, status, tytuł, czas i suma kontrolna.
- `report.json`: diagnostyka PZPS i Pomorskiej III ligi.
- `2liga-extracted.json`: odczyt z PZPS, z poprawionymi kolumnami tabel oraz adresami logotypów.
- `3liga-extracted.json`: połączony terminarz i wyniki, godziny, wyniki setów, tabela i adresy logotypów.
- `2liga-volleystation-extracted.json`: komplet pięciu grup II ligi z VolleyStation,
  godzinami uzupełnionymi z PZPS, tabelami i adresami logotypów.
- `2liga-volleystation-report.json`: liczby meczów i test spójności wyników z tabelami.

Katalog artefaktów jest ignorowany przez Git. Podsumowanie wykonanego testu jest
w [`RESULTS.md`](RESULTS.md). Adresy logotypów pochodzą z HTML; test nie pobiera
osobno wszystkich plików obrazków. Godziny pozostają w lokalnym formacie źródła.
Brakujące dane nie są zgadywane. `time_source` w eksporcie II ligi wskazuje źródło godziny.

Zweryfikowane zachowanie endpointu `webapi.php`, dostępne pola i sprawdzone parametry
opisano w [`PZPS_API.md`](PZPS_API.md).

Testy nie uruchamiają Chromium, Puppeteera ani stealth i nie importują ciasteczek
z przeglądarki. Odmowa HTTP lub strona weryfikacji daje błąd; kod nie próbuje ich
omijać. HTTP 200 zaobserwowane z tego środowiska nie gwarantuje dostępu z innego hostingu.
