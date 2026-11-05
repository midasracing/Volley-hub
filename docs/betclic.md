# Klient kursów Betclic

Opcjonalny klient Pythona do **odczytu kursów na zwycięzcę całego meczu siatkówki
z Polski, Włoch i Japonii**. Domyślnie pobiera wszystkie trzy kraje.
Eksportuje JSON; nie dodaje kursów do interfejsu aplikacji ani nie uruchamia cyklicznego pobierania.
Nie pobiera wyników, setów ani rynków na dokładny rezultat.

## Instalacja

Wymagane: Python 3.10+, Git oraz dostęp sieciowy. Z katalogu repozytorium:

```bash
python3 -m venv .venv-betclic
source .venv-betclic/bin/activate
python -m pip install -r requirements-betclic.txt
```

Na Windows aktywuj środowisko przez `.venv-betclic\Scripts\activate`.
Zależność [TapsHTS/betclic-api](https://github.com/TapsHTS/betclic-api) jest przypięta do
commita [`5989c09`](https://github.com/TapsHTS/betclic-api/commit/5989c0936e17c98fff392dc20f5d2e8e4048c04e).
Autor deklaruje licencję MIT w metadanych pakietu. To nieoficjalny klient API oferty Betclic;
działanie i format zewnętrznego źródła mogą się zmienić.

## Pobranie danych

```bash
# Polska, Włochy i Japonia; JSON na standardowym wyjściu
python scripts/betclic_odds.py

# Tylko Polska; zapis do pliku
python scripts/betclic_odds.py --country pl --output /tmp/betclic-poland.json

# Wybrane kraje: Włochy i Japonia
python scripts/betclic_odds.py --country it --country jp
```

Klient uwzględnia krajowe rozgrywki kobiet i mężczyzn, które są dostępne w ofercie.
Rozpoznaje francuskie prefiksy nazw rozgrywek: `Pologne`, `Italie`, `Japon`.
Pomija inne kraje, rozgrywki międzynarodowe, pozycje bez rozpoznanego kraju oraz
wydarzenia bez dwóch drużyn, np. rynek na zwycięzcę całego sezonu.
Nie wymaga ręcznego podawania ID lig.

W testach 4 listopada 2026 r. kategoria `41288` zawierała drużyny PlusLigi,
mimo nazwy „Tauron Liga H.” w źródle. Nie należy
utożsamiać jej automatycznie z TAURON 1. Ligą. Nie potwierdzono dostępności tej ostatniej.
Nazwy drużyn pozostają zgodne ze źródłem, które np. BOGDANKĘ LUK Lublin nazywało
„Politechnika Lublin”. Do późniejszego łączenia z danymi ligowymi potrzebne jest jawne
mapowanie drużyn; dopasowanie wyłącznie po nazwie byłoby zawodne.

Domyślnie klient czyta maksymalnie 5 stron listy siatkówki i pobiera szczegóły
maksymalnie 40 pasujących meczów. Limity można ustawić przez `--max-pages` i
`--max-matches`. Filtr kraju jest stosowany przed pobieraniem szczegółów.
Puste strony kończą paginację; powtórzenie strony albo osiągnięcie limitu daje
`truncated: true` i komunikat na stderr. Taki eksport nie potwierdza kompletności oferty.

## Format i zachowanie

- `source`, `sport`, `countries`, `fetched_at`: pochodzenie, kraje i czas ukończenia pobrania w UTC.
- `truncated`: czy lista może być niepełna z powodu limitów lub powtarzanych stron.
- `matches`: ID meczu, kraj, nazwa źródłowa, termin, rozgrywki, drużyny i `winner_market`.
- `winner_market`: nazwa rynku i dwie pozycje `name` / `odds`, albo `null`, jeśli
  brakuje aktywnego, poprawnie rozpoznanego rynku. `null` nie oznacza kursu zero.
- ID są eksportowane jako ciągi znaków. Kursy są liczbami dziesiętnymi.

Klient korzysta z francuskiej lokalizacji źródła i rozpoznaje dokładną nazwę
`Vainqueur du match`. Pomija rynki zawieszone, niepoprawne kursy, zwycięzców setów
i dokładne wyniki. Zmiana nazwy rynku po stronie API wymaga aktualizacji filtra;
klient nie zgaduje znaczenia innych rynków. Status live z parsera upstream nie jest
eksportowany, ponieważ jego poprawność nie została potwierdzona.

W odróżnieniu od transportu upstream skrypt odczytuje pierwszą pełną paczkę danych
i zamyka strumień powiadomień, zamiast czekać na dalsze aktualizacje. Ma timeouty
połączenia/odczytu, limit czasu zbierania paczki oraz limity rozmiaru i liczby ramek.
Błędy HTTP, gRPC i niepełne dane kończą proces kodem `1`. Plik wskazany przez
`--output` jest zastępowany atomowo dopiero po udanym pobraniu całości; błąd pozostawia
poprzedni plik. Czas `fetched_at` pozwala wykryć jego nieaktualność.

W testach publiczny odczyt nie wymagał tokena. Klient nie omija odpowiedzi odmownych
API ani nie ponawia automatycznie żądań. Dostępność meczu lub kursów nie jest gwarantowana.

## Testy bez sieci

```bash
python -m unittest discover -s tests -p 'test_betclic_odds.py' -v
```

Testy sprawdzają m.in. fragmentację ramek, zakończenie odczytu przed kolejną aktualizacją,
rzeczywisty parser przypiętej zależności, błędy transportu, paginację, filtr rynku
oraz zachowanie poprzedniego eksportu po błędzie. CI nie odpytuje oferty Betclic.

Pełny test sieciowy 5 listopada 2026 r. o 15:12 UTC zwrócił 7 polskich meczów
z kursami, w tym mecz męskiej ligi, z `truncated: false`. W tej odpowiedzi nie było
meczów włoskich ani japońskich, więc ich rzeczywistej oferty kursów nie potwierdzono.
