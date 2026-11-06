# VolleyStation: wyniki prób po przeglądzie rekomendacji społeczności

**Najlepszy nowy kandydat to SeleniumBase UC + CDP: 4/4 kompletne odświeżenia,
12/12 poprawnych odczytów w dwóch niezależnych zadaniach GitHub Actions.
Pure CDP z obsługą challenge: 2/2 odświeżenia, 6/6 odczytów.**

Nie wszystkie konfiguracje są blokowane. Wcześniejsze Stealth/Rebrowser/Patchright
dostawały 403, a nowe warianty CDP odczytały komplet danych przy aktywnym challenge.
To mocniejszy wynik niż wcześniejsze próby Stealth, ale krótka seria nie dowodzi
bezobsługowej pracy przez wiele dni. Niczego nie wdrażano do produkcji.

## Co polecali autorzy narzędzi

- [SeleniumBase, komentarz maintenera do #4460](https://github.com/seleniumbase/SeleniumBase/issues/4460#issuecomment-5267111319):
  zachować przypięte zależności Selenium, aktywować CDP przed nawigacją,
  używać metod CDP oraz wbudowanej obsługi challenge. Zwykłe `driver.get()`
  pomija tę inicjalizację. Sprawdzono zarówno UC + CDP, jak i Pure CDP.
- [Camoufox, zamknięcie #442](https://github.com/daijro/camoufox/issues/442#issuecomment-6567564672):
  zapisać wynik `generate_fingerprint()` i przekazywać go przy każdym starcie
  z tym samym profilem. Autor rozróżnia stabilne piksele `getImageData()`
  od rotującego między procesami PNG z `toDataURL()`.
- [Camoufox #311](https://github.com/daijro/camoufox/issues/311):
  w zgłoszeniach pojawiają się różnice między kontenerem a zwykłym systemem,
  mimo tego samego skryptu. Dlatego zmierzono rzeczywisty ekran, fonty, canvas
  i dostępność WebGL, zamiast porównywać wyłącznie opcje startowe.

Są to rekomendacje i relacje z konkretnych zgłoszeń, nie gwarancje działania
na VolleyStation. Poniższe wyniki pochodzą z własnych prób tego źródła.

## Metoda i kompletność

Wszystkie próby używały izolowanej kopii parsera i wcześniej zweryfikowanego cache:
72 mecze z godzinami, 17 zakończonych z punktami wszystkich setów, 9 drużyn
z logotypami. Każda aktualizacja pobierała świeżo terminarz, wyniki i tabelę.
Punkty niezmienionych zakończonych meczów i logotypy pochodziły z cache.
To próby odświeżania, a nie pobrania całego sezonu od zera.

Każdy cykl zaczynał się od nowej przeglądarki i nowego profilu. Między nawigacjami
zachowano co najmniej 15 s, między cyklami 30 s; limit wynosił 12 nawigacji
na scenariusz. Po pierwszej odmowie lub niepoprawnym dokumencie kończono scenariusz.
Pomocnik obsługi challenge był wywoływany najwyżej raz na dokument, tylko po jego
wykryciu. Nie korzystano z płatnej usługi rozwiązywania CAPTCHA.

Mierzono końcowy status głównego dokumentu, DOM i wynik parsera. Sam powrót
z funkcji obsługi challenge nie oznaczał sukcesu. Sześć jej wywołań zakończyło się
poprawnym dokumentem HTTP 200; każde miało początkowy challenge i dwie odpowiedzi
głównego dokumentu. Bez eksperymentu z losowym przydziałem nie dowodzi to,
że sam pomocnik był konieczny w każdym przypadku.

Każde zadanie sieciowe miało kontrolę zwykłym HTTP. Wszystkie **9/9 kontroli
zwróciły 403/challenge**. Różne warianty pracowały na różnych runnerach;
nie wyizolowano wpływu adresu IP. Limit równoległości wynosił dwa zadania
w obrębie workflow; uruchomienia poprawkowe częściowo nakładały się w czasie.
Liczby dokumentów nie obejmują zasobów strony i nawigacji wewnętrznych challenge.

## Wyniki

| Wariant | Poprawne dokumenty | Kompletne aktualizacje | Ustalenie |
| --- | ---: | ---: | --- |
| SeleniumBase UC + CDP, pierwsze zadanie | 6/6 | 2/2 | Challenge obsłużony w obu nowych sesjach |
| SeleniumBase UC + CDP, drugie zadanie | 6/6 | 2/2 | Wynik powtórzony na kolejnym runnerze |
| SeleniumBase Pure CDP + obsługa challenge | 6/6 | 2/2 | Poprawny import, w tym strony z początkowym challenge |
| Pure CDP, samo oczekiwanie, po poprawce startu | 1/2 | 0/1 | Terminarz poprawny, wyniki 403 |
| Pure CDP, samo oczekiwanie, pierwsza konfiguracja | 0/1 | 0/1 | Terminarz 403 |
| Camoufox, domyślne dodatki, Linux i ekran 1920×1080 | 6/6 | 2/2 | Kompletne odświeżenia |
| Camoufox, bez uBlock Origin | 0/1 | 0/1 | Pierwszy dokument 403 |
| Camoufox, bez uBlock + wymuszone renderowanie programowe | 0/1 | 0/1 | Pierwszy dokument 403 |
| Pure CDP + obsługa challenge, pierwszy start | 0/0 | — | Błąd startu; nie testował Cloudflare |

Łącznie wykonano **29 nawigacji**, z których **25** zwróciło poprawne dane.
Uzyskano **8 kompletnych aktualizacji**. Nie należy traktować tej proporcji
jako estymacji niezawodności: scenariusze mają różną długość i kończą się
po pierwszej odmowie. Zaplanowane, niewykonane cykle nie są porażkami.

Wszystkie osiem kompletnych eksportów przeszło dodatkowy, niezależny od kontroli
kompletności test: legalność punktów, zgodność zwycięzców setów z wynikiem meczu,
brak powtórzonych ID oraz zgodność rozegranych meczów, zwycięstw, porażek,
punktów ligowych, setów i małych punktów z tabelą.
[Zapis kontroli i skróty eksportów](kontrola-eksportow.json).

Pierwszy Pure CDP z obsługą challenge nie połączył się z przeglądarką.
Przy domyślnym uruchomieniu biblioteka zakładała własny ekran wirtualny;
w wariancie, który wystartował, przeglądarka widziała 1366×768 mimo zewnętrznego
Xvfb 1920×1080. W poprawce jawnie wybrano `headed=True`, zachowując zewnętrzny
ekran. Ponowiono tylko rodzinę SeleniumBase. W poprawionym zadaniu potwierdzono
zarówno ekran X, jak i ekran widziany przez przeglądarkę: 1920×1080.
Nie ustalono jednoznacznie przyczyny pojedynczego błędu startu.

## Fingerprint: co rzeczywiście pozostaje stałe

Osobne zadanie używało wyłącznie własnego serwera localhost: **zero żądań
do VolleyStation**. Porównano trzy uruchomienia tego samego profilu dla zapisanych
opcji, oficjalnego API zapisanego fingerprintu i zwykłego Firefoksa.
W każdym procesie wykonano dwa odczyty tego samego canvas.

| Sposób restartu | Cechy poza rozmiarem okna | Piksele canvas | PNG canvas | Cookie po restarcie |
| --- | --- | --- | --- | --- |
| Camoufox, zapisane opcje startu | stałe 3/3 | stałe 3/3 | zmienia się między procesami | zachowane |
| Camoufox, zapisany fingerprint przez API | stałe 3/3 | stałe 3/3 | zmienia się między procesami | zachowane |
| Zwykły Firefox 153.0 | stałe 3/3 | stałe 3/3 | zmienia się między procesami | zachowane |

Porównywane cechy obejmowały UA, platformę, języki, liczbę rdzeni, strefę czasową,
ekran, pomiary czterech fontów i WebGL. Piksele odczytane przez WebGL również
były stałe. To ograniczony zestaw sond, nie cały fingerprint zbierany przez Cloudflare.

Camoufox zmienił po drugim starcie wysokość obszaru treści z 683 na 635 pikseli,
przy tym samym zewnętrznym oknie 1366×768; trzeci start wrócił do 683.
Dlatego pełny skrót wszystkich zmierzonych cech nie był stały, mimo zgodności
pozostałej tożsamości. Nie ustalono przyczyny zmiany wysokości. Wszystkie odczyty
w obrębie jednego procesu były stałe.

Rotujący skrót PNG wystąpił także w zwykłym Firefoksie. Sam w sobie nie dowodzi
utraty fingerprintu ani przyczyny blokady. Oficjalny zapis fingerprintu działał
w badanych cechach, lecz nie dał tu przewagi nad zapisaniem kompletnych opcji.

Pierwsza wersja testu cookies czytała zmienną globalną strony. Camoufox izoluje
świat wykonywania `evaluate`, więc odczyt zwracał `null`; był to błąd pomiaru,
nie dowód utraty cookies. Poprawka przeniosła informację od serwera do atrybutu DOM.
Powtórzono tylko test offline. Serwer potwierdził cookie na drugim i trzecim starcie
we wszystkich trzech wariantach. Surowe dane zachowują również błędny pierwszy pomiar.

W sondzie uruchamianej przed wejściem na źródło SeleniumBase nie udostępniał WebGL,
a mimo to UC + CDP przechodził próby. Działający Camoufox udostępniał WebGL.
Nie ma podstaw, aby uznać samo włączenie WebGL albo wyłączenie dodatku za rozwiązanie
problemu. Nie uzyskano przewagi wariantu renderowania programowego.

## Rekomendacja po próbach

Do następnego etapu wybrałbym **SeleniumBase UC + CDP**, z Pure CDP jako drugim
kandydatem i Camoufox jako alternatywą. UC + CDP ma w tej serii powtórzony wynik
w dwóch zadaniach, a nie tylko na jednym runnerze. Nadal brakuje wielodniowych prób,
próby nowych wyników wymagających pobrania szczegółów i pełnego importu od zera.

Nie obiecuję rozwiązania „bulletproof”. Dla wymaganej stałej dostępności nadal
warto uzgodnić feed/API lub dostęp z VolleyStation. Scraper powinien zachowywać
ostatnie dobre dane, sprawdzać kompletność i publikować atomowo; błąd parsera
długich setów opisany w poprzednim raporcie nadal wymaga poprawy przed wdrożeniem.
Nowe pomiary uzasadniają pilotaż CDP, nie automatyczne wdrożenie do produkcji.

## Odtworzenie i dowody

- [Pierwsza seria](https://github.com/midasracing/kiedysiatka/actions/runs/42297682083),
  commit `ccd58abfe2d24dd55931b8b445d1c7e441fee36f`.
- [Powtórka SeleniumBase](https://github.com/midasracing/kiedysiatka/actions/runs/42298090306),
  commit `4c19c72db6b4c821199501136cceed88c409dcda`.
- [Poprawiony pomiar restartów](https://github.com/midasracing/kiedysiatka/actions/runs/42298531363),
  commit `481e1e1cfc76f7c77c9a426e9c242b60c3541910`.
- [Surowe podsumowania, sondy i żądania](dane-pomiarowe.json), [CSV](wyniki.csv),
  [pełna tabela prób](tabela.md), [identyfikatory i skróty artefaktów](artefakty.json).

SeleniumBase **4.57.1**, Selenium **4.52.0**; Camoufox **0.5.9**, przeglądarka
**158.0.1-beta.41**. Workflow jest przypięty do gałęzi eksperymentalnej, ma tylko
`contents: read` i nie publikuje feedu. Wszystkie **9/9** kontroli skrótu
produkcyjnego pliku potwierdziły brak zmian. Nie zapisano prywatnych profili
ani wartości cookies z serwisu. Zielony status zadania oznacza zakończenie pomiaru.

Przykład odtworzenia wariantu UC + CDP na Linuksie z Chrome i Xvfb:

```bash
python -m pip install -r experiments/volleystation/requirements-seleniumbase.txt
LAB_BROWSER=/usr/bin/google-chrome xvfb-run -a --server-args="-screen 0 1920x1080x24" \
  python experiments/volleystation/community_selenium.py --case sb-uc-cdp-solve
```

Wyniki trafiają wyłącznie do `outputs/community/`. Generator zestawienia
`make_community_report.py` odczytuje rozpakowane artefakty wskazanych trzech runów;
nie wykonuje żądań do źródła.
