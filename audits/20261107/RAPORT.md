# Audyt II ligi i Pomorskiej III ligi względem oficjalnych stron i feedów TAURON

**Po poprawkach: 604/604 mecze zgodne w sprawdzanych polach, 604 godziny,
169 kompletnych wyników zakończonych spotkań, jeden mecz LIVE, 63 wiersze tabel
i 63 działające logotypy. UC + CDP i Camoufox zwróciły zgodne dane.**

Wspólny format obejmuje 29 pól, w tym wszystkie 28 pól występujących we wszystkich
meczach zapisanych feedów TAURON Ligi i TAURON 1. Ligi oraz opcjonalne `broadcast`.
**To zgodność struktury i podstawowych danych, nie pełna równość pokrycia metadanych.**
Hala i numer terminu pozostają `null`, gdy sprawdzone źródło ich nie potwierdza.
Sam znacznik „TV” nie dostarcza nazwy kanału. Strony sześciu oznaczonych meczów
zawierają jednak konkretne odtwarzacze YouTube; ich URL trafia teraz do `broadcast_urls`.

**Uzupełnienie audytu transmisji, 07.11.2026, 12:31–12:32 UTC:** wcześniejsza
wersja audytu sprawdziła znaczniki TV, ale pominęła osadzone odtwarzacze. Ponowny
odczyt wszystkich sześciu stron przez UC + CDP potwierdził sześć adresów YouTube:
dwa dla spotkań zaplanowanych i cztery dla zakończonych. Poprawiono importer,
snapshot II ligi i aplikację. [Dowody i czasy odczytów](broadcasts.json).
Linki są potwierdzone na stronie ligi; nie testowano odtwarzania na YouTube.

| Data i godzina ze źródła | Mecz zaplanowany | Link opublikowany przez ligę |
| --- | --- | --- |
| 07.11.2026, 17:00 | Volley Team Żychlin – ProNutiva SKK Belsk Duży | [YouTube](https://www.youtube.com/watch?v=nDOImTNf7_o) |
| 07.11.2026, 18:00 | Instytut Mechaniki Rekord Volley Jelcz-Laskowice – KS Bielawianka-Bester | [YouTube](https://www.youtube.com/watch?v=38BPqJpf0HU) |

## Zakres i wyniki

| Zakres | Mecze / ze źródła | Z godziną | Zakończone z pełnymi setami | LIVE | Drużyny / tabela |
| --- | ---: | ---: | ---: | ---: | ---: |
| II liga, grupa 1 | 90/90 | 90 | 21 | 0 | 10/10 |
| II liga, grupa 2 | 110/110 | 110 | 34 | 0 | 11/11 |
| II liga, grupa 3 | 132/132 | 132 | 42 | 0 | 12/12 |
| II liga, grupa 4 | 90/90 | 90 | 21 | 0 | 10/10 |
| II liga, grupa 5 | 110/110 | 110 | 34 | 0 | 11/11 |
| Pomorska III liga | 72/72 | 72 | 17 | 1 | 9/9 |

Każda tabela zgadza się z zakończonymi wynikami: rozegrane mecze, zwycięstwa,
porażki, punkty ligowe, sety i małe punkty. Meczu trwającego nie doliczano do tabeli.
Wszystkie zakończone mecze mają legalne punkty setów i zgodną liczbę wygranych setów.
Zweryfikowano 63/63 adresy obrazów: HTTP 200 i typ zawartości `image/*`.

Przed zmianami feed II ligi zawierał 145 zakończonych wyników, brakowało 335 godzin,
a w grupie 4 sześć wierszy tabeli nie zgadzało się z dostępnymi wynikami.
Pomorska miała 15 zakończonych wyników i jeden mecz bez godziny.
Wszystkie 604 rekordy miały braki względem pełnego formatu TAURON.
Część różnicy w liczbie wyników wynika z nowszego odczytu źródła.
Nie przeliczano tabel w celu ukrycia braków: nowy odczyt opiera się na opublikowanych tabelach i sprawdza ich zgodność.

## Naprawione problemy

1. **Niepełny wynik był błędnie zakończonym meczem.** W terminarzu GKS Stoczniowiec
   Gdańsk — KATS ALPAT CYMMAT GDYNIA widniało 1:1. Dotychczasowy parser nazywał każdy
   wynik setowy `finished`. Nowy parser rozróżnia `scheduled`, `live`, `finished`;
   zakończenie wymaga trzech wygranych setów.
2. **Trwający wynik nie może być zamrożony w cache.** Szczegóły LIVE są odczytywane
   przy każdej aktualizacji. W późniejszym odczycie tego samego meczu było 2:1
   z setami 25:17, 20:25, 25:20. Zmianę 1:1 → 2:1 zapisano w raporcie jako zmianę
   między przechwyceniami. Nie uznano obu chwilowych stanów za równoczesną sprzeczność.
   Gdy źródło publikuje punkty bieżącego seta, trafiają do `current_points`, osobno
   od zakończonych setów. W tym przechwyceniu bieżących punktów nie było, więc pole ma `null`.
3. **Ukryte „TV” nie oznacza transmisji.** HTML zawiera taki napis przy każdym
   meczu, lecz CSS ukrywa go poza `.stage.live`. Uznawane są widoczne znaczniki:
   sześć w II lidze, zero w Pomorskiej. Dla tych sześciu meczów odczyt strony
   szczegółów potwierdził filmy YouTube. Linki odświeżają się w każdym cyklu,
   także gdy punkty zakończonego meczu pochodzą z PZPS lub cache. Usunięty
   odtwarzacz usuwa poprzedni URL. Karta pokazuje „Transmisja · YouTube” albo
   „Nagranie · YouTube”; samo „TV” nie tworzy linku.
4. **ID logotypu nie jest ID drużyny.** Przykładowo profil Stoczniowca ma ID
   `2103916`, a plik logotypu `2122546`. `home_team_id`, `away_team_id` i `teams[].id`
   pochodzą teraz z odnośników profili; numer pliku jest osobnym `badge_id`.
5. **Bezpieczne łączenie źródeł II ligi.** PZPS miał tylko 198 godzin w terminarzu.
   VolleyStation uzupełnia godziny spotkań zaplanowanych. Uzupełnienia PZPS wymagają
   dokładnej daty i kierunku gospodarz–gość, zgodnych nazw po normalizacji oraz
   zgodnego wyniku. Nie stosuje się przybliżonych prefiksów ani wyboru pierwszego rewanżu.
6. **Sześć wyników wymagało własnych szczegółów VolleyStation.** Dla 146 zakończonych
   meczów II ligi punkty pochodziły z bezpiecznie dopasowanych, świeżych wierszy PZPS;
   dla pozostałych sześciu odczytano strony meczów VolleyStation.
7. **Format odpowiada TAURON.** Dodano datę ISO, oficjalne ID meczu, ID i logotypy
   drużyn przy meczu, `set_points`, sumy `home_points`/`away_points`, fazę,
   numer kolejki i meczu, metadane sprawdzenia oraz jawne nieznane wartości.
   Migracja na oficjalne ID nie powoduje utraty bezpiecznego cache.

## Sposób sprawdzenia

Zarejestrowano **75 dokumentów przez rzeczywiste przeglądarki**: po 22 strony
główne dla UC + CDP i Camoufox, sześć stron szczegółów II ligi przez UC + CDP
oraz 19 stron meczów Pomorskiej przez Camoufox — wszystkie 17 zakończonych
i dwie z terminarza, w tym mecz LIVE, oraz sześć stron z transmisjami przez UC + CDP.
Szczegóły są współdzielonym materiałem
kontrolnym; nie wykonano podwójnego odczytu każdego szczegółu przez oba silniki.

Audyt czyta karty meczów niezależnym czytnikiem DOM, porównuje daty, godziny,
kierunek drużyn, wynik, status, rundę, numer meczu, oficjalne ID, obrazy i widoczne
znaczniki TV z emisją importera. Oddzielnie odczytuje wiersze tabel i punkty
setów ze stron meczów lub wierszy PZPS. Sprawdza pochodne pola punktowe
i kompletność pól referencyjnych. Osobny odczyt DOM odtwarzaczy sprawdza także
adresy transmisji. Po uzupełnieniu przechwyceń ponownie odtworzono oba importy:
604 mecze bez różnic w sprawdzanych polach, w tym sześć zgodnych URL filmów.
Nie wykonywano ponownie odczytu wszystkich stron głównych ani nowych prób Camoufox.
Samo porównanie dwóch uruchomień tego samego
parsera nie stanowiło całego audytu.

Porównano też rzeczywiste HTML stron terminarzy TAURON Ligi i 1. Ligi, a kontrakt
pól wyznaczono z obu istniejących feedów: 182 i 240 meczów.
Surowe HTML pozostają w lokalnych artefaktach; opublikowane są URL, status,
czas przechwycenia, SHA-256 i wyniki porównania. Daty `updated_at` w zapisanych
snapshotach odnoszą się do przechwycenia źródła, nie do późniejszego odtworzenia audytu.

Źródła: [II liga VolleyStation](https://2ligamezczyzn.volleystation.com/pl/teams/),
[PZPS — terminarz](https://sedziowie.pzps.pl/system/mecze-II-liga-mezczyzn/),
[PZPS — wyniki](https://sedziowie.pzps.pl/system//index.php?mode=12&type=9),
[Pomorska — terminarz](https://pomorskie.volleystation.com/pl/phase-6796-pomorska-iii-liga-meska/schedule/),
[TAURON](https://www.tauronliga.pl/games/nocookies/1.html),
[TAURON 1. Liga](https://www.tauron1liga.pl/games/nocookies/1.html).

## Co nadal różni się od TAURON

- **Hale:** feedy referencyjne mają je przy 182/182 i 240/240 meczach.
  Sprawdzone widoki VolleyStation nie potwierdziły tych danych. `venue=null`.
  Nie sprawdzano osobno wszystkich 604 stron meczów w celu poszukiwania hali.
- **Numer terminu:** TAURON publikuje tę informację; nie zastąpiono jej zgadywaną
  kopią numeru rundy. `term_number=null`.
- **Transmisje:** widoczny znacznik TV zachowano jako `['TV']`; sześć potwierdzonych
  odtwarzaczy ma dodatkowo `broadcast_urls`, `broadcast_source_url` i
  `broadcast_checked_at`. Nie skanowano stron wszystkich nieoznaczonych spotkań
  ani kanałów klubowych w poszukiwaniu dodatkowych emisji. Nie badano dostępności
  nagrań, ograniczeń regionalnych ani rozpoczęcia transmisji na YouTube.
- **LIVE:** potwierdzono odczyt aktualnego stanu meczu i regresję dla punktów
  trwającego seta. Nie potwierdzono ciągłego strumienia punkt po punkcie;
  domyślny harmonogram importera nadal ma 15 minut przerwy między cyklami.

Próby wykonano w zarządzanym środowisku z proxy HTTPS i włączoną weryfikacją TLS.
Nie potwierdzają wielodniowej dostępności z dowolnego IP.

## Wyniki i powtórzenie

- [Raport maszynowy i manifest stron](report.json)
- [Stan przed](before.json) i [po](after.json)
- [Kontrakt referencyjny TAURON](reference.json)
- [Lista 604 meczów CSV](matches.csv)
- [Sprawdzenie 63 logotypów](logos.json)
- [Sześć transmisji/nagrań i manifest dodatkowych stron](broadcasts.json)
- Zaktualizowane snapshoty: [II liga](../../data/2liga.json), [Pomorska III liga](../../data/pomorska3liga.json).

Kontrole: **39 testów Python** (22 lokalnego importera, 9 regresji audytu,
8 istniejących regresji ligowych) i **23 testy frontendu/danych** zakończyło
się poprawnie. Build produkcyjny aplikacji również przeszedł. W Chromium sprawdzono
wszystkie dwa linki transmisji i cztery linki nagrań w widokach 390 i 1280 px:
bez błędów JavaScript i poziomego przewijania.

Przechwycenie źródeł bez płatnych usług, osobno dla każdego silnika:

```bash
python -m local_scraper.capture_audit --engine seleniumbase --output .local-scraper/parity-captures
python -m local_scraper.capture_audit --engine camoufox --output .local-scraper/parity-captures
python -m local_scraper.audit --captures .local-scraper/parity-captures --output .local-scraper/parity-report
```

Wymagane jest okno przeglądarki lub Xvfb. Opcje `--browser` i `--camoufox-ca`
działają tak jak w importerze. Przechwycenie ma odstępy 15 s i może potrwać
kilkanaście minut. W razie zmiany wyniku w trakcie odczytów audyt zachowuje
informację o zmianie; sprzeczność, której nie da się bezpiecznie wyjaśnić,
pozostaje błędem. Odtworzenie już pobranych HTML nie wykonuje żądań do źródła.
