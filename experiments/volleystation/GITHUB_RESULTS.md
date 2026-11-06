# Próby VolleyStation na GitHub Actions — 6 listopada 2026

To raport wstępny. Wyniki rozszerzonych testów, powtarzalności i końcowa rekomendacja:
[RAPORT_KONCOWY.md](report-final/RAPORT_KONCOWY.md).

**Camoufox z interfejsem i import przyrostowy pozwoliły raz odświeżyć kompletny
feed w sześciu odczytach stron. Nie uzyskano rozwiązania bulletproof: ponowny
start przeglądarki z zachowanym profilem i konfiguracją fingerprintu zakończył się 403.**

Wszystkie próby wykonano na osobnej gałęzi `experiment/volleystation-20261106`.
Workflow miały uprawnienia wyłącznie do odczytu repozytorium. Nie aktualizowały
produkcyjnych feedów, scrapera ani wdrożenia strony.

## Porównanie

| Wariant | Wynik na GitHub Actions |
| --- | --- |
| `requests` | 403 z challenge, również w próbach kontrolnych obok Camoufox |
| Puppeteer + Stealth | 403 zarówno headless, jak i z interfejsem |
| Rebrowser Puppeteer | 403 zarówno headless, jak i z interfejsem |
| Patchright | 403 zarówno headless, jak i z interfejsem |
| `curl_cffi` z impersonacją Chrome | 403 |
| Camoufox headless | Terminarz i wyniki poprawne; tabela zablokowana: 2/3 stron |
| Camoufox z interfejsem przez Xvfb | Terminarz, wyniki, tabela i drużyny poprawne: 4/4 stron |

Źródła:

- [Chrome, HTTP, Stealth, Rebrowser i Patchright](https://github.com/midasracing/kiedysiatka/actions/runs/42212453568)
  — commit `43eb2d115ea1416a0da6ac1ab388430dc90a9e90`.
- [Firefox i curl_cffi](https://github.com/midasracing/kiedysiatka/actions/runs/42213214158)
  — commit `a93fbeb52f2fb7b511594dc4835e73c00a58eb4b`.

Po odmowie dostępu silnik kończył próby. Planowanych kolejnych stron ani drugiej
serii nie wykonywano. Nie należy interpretować zatrzymanego testu jako dziesięciu
nieudanych odczytów. Porównywaliśmy rekordy parsera, nie sam status HTTP 200.

## Pełny import od zera

[Dłuższa próba Camoufox](https://github.com/midasracing/kiedysiatka/actions/runs/42213719300)
odczytała 14 stron. Piętnasty odczyt dostał challenge i HTTP 403. Powstał niepełny
eksport: brak świeżej tabeli i logotypów, część meczów bez godzin oraz punktów setów.
Kontrola jakości miała `quality_passed: false`; pliku nie publikowano.

## Import przyrostowy

[Próba przyrostowa](https://github.com/midasracing/kiedysiatka/actions/runs/42214482012)
— commit `7f05f0c172b1ddfa7b16288a32abeb588276b7ae`:

- Zwykły HTTP do tej samej strony na tym samym runnerze dostał 403/challenge.
- Zachowano punkty setów 14 zakończonych meczów z poprzedniego feedu, po sprawdzeniu
  dokładnej tożsamości i niezmienionego oficjalnego wyniku. Dane niepełne lub
  niezgodne wymagają ponownego pobrania.
- Logotypy 9 drużyn wykorzystano z poprzedniego feedu. Nie stanowi to ich ponownej
  weryfikacji u źródła. Sześć testów offline sprawdza reguły ponownego użycia danych.
- Sześć odczytów przez Camoufox dało kompletny eksport: **72 mecze z godzinami,
  17 zakończonych z kompletem punktów setów, 9 drużyn z logotypami i 9 wierszy tabeli**.
- Eksport miał `quality_passed: true`. Kontrola SHA-256 potwierdziła brak zmian
  produkcyjnego feedu.
- Po restarcie przeglądarki z tym samym prywatnym profilem i tym samym zestawem
  wygenerowanych opcji fingerprintu pierwszy odczyt ponownie dostał 403.
  `restart_passed: false`. Dalszych żądań nie wykonywano.

Kopia z optymalizacją: `scraper_incremental.py`. Powtarzalna próba:
`camoufox_incremental.py` i workflow `experiment-volleystation-incremental.yml`.
Kopie pierwotnego scrapera i wcześniejsze pomiary pozostają osobno.

## Ograniczenia i wniosek

Zadania korzystały z różnych runnerów i adresów wyjściowych. W obrębie pojedynczego
zadania silniki dzieliły runner, ale między zadaniami nie można oddzielić wpływu
biblioteki od wpływu sieci. Wyniki wskazują, że Camoufox jest obiecującym kandydatem;
nie dowodzą, że sam tryb z interfejsem powoduje poprawę.

Przyrostowe pobieranie zmniejsza ruch z 30 do 6 odczytów stron dla sprawdzonego
stanu feedu. Nie obejmuje to dodatkowych żądań przeglądarki po skrypty, obrazy i inne
zasoby. Liczba potrzebnych odczytów wzrośnie przy nowych meczach, zmianach wyników
lub braku danych w cache.

Udany pojedynczy import nie potwierdza działania kolejnych zadań ani całego sezonu.
Nie ma podstaw do obietnicy stabilnego, bezobsługowego obejścia Cloudflare.
Przy wdrażaniu należałoby zachować kontrolę kompletności przed publikacją,
monitorować świeżość feedu i uzgodnić dostęp/API z VolleyStation lub sprawdzić
stałe środowisko wykonawcze. Nie wdrażano tych zmian do produkcji.

Zielony status workflow oznacza zakończenie pomiarów, nie przejście Cloudflare.
Właściwe wyniki znajdują się w logach i plikach `summary.json` w artefaktach.
