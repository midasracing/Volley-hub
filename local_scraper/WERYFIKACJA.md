# Weryfikacja lokalnego importera

Wersję sprawdzono 6–7 listopada 2026 na Linuksie, z Pythonem 3.12,
Chromium 156, SeleniumBase 4.57.1, Selenium 4.52.0, Camoufox 0.5.9
i przeglądarką Camoufox 158.0.1-beta.41. Przeglądarki działały z interfejsem
na ekranie Xvfb 1920×1080.

## Wyniki

- **21 testów nowego importera: poprawne.** Sprawdzono między innymi kontrolowane
  awarie, blokadę równoczesnego zapisu, zachowanie poprzedniego feedu, timeout
  z procesem potomnym, HTTP 200 zawierający challenge, 429 i trwałą przerwę,
  cache, wznowienie przerwanego importu, legalne długie sety i zgodność tabeli.
- **8 istniejących testów regresyjnych: poprawne.** Dwie próby dotyczą niższych
  lig, sześć — odświeżania tabeli TAURON.
- Kontrola wymaganych pakietów `pip check`: poprawna. Kontrola składni,
  importów i formatowania nowych plików: poprawna.
- Obie rzeczywiste przeglądarki odczytały własną stronę testową przez lokalny
  serwer: HTTP 200 i oczekiwany DOM.
- **UC + CDP wykonał rzeczywisty kompletny import:** 6 poprawnych dokumentów,
  72 mecze, 17 zakończonych z pełnymi setami, 9 drużyn i wierszy tabeli.
  Wykorzystano 14 znanych szczegółów, pobrano 3 brakujące. Wynik powtórzono
  po dodaniu profili zarządzanych przez proces nadrzędny.
- **Camoufox poprawnie przejął import po wymuszonej awarii uruchomienia Chrome.**
  Z kompletnym cache wystarczyły 3 dokumenty do odświeżenia takiego samego
  kompletnego zestawu danych. To test rzeczywistego przełączenia procesu,
  a nie symulowana odpowiedź przeglądarki.
- Powtórka 7 listopada sprawdziła przełączenie z niepełnym cache: Camoufox
  wykonał 6 poprawnych odczytów, uzupełnił 3 brakujące szczegóły i zapisał je
  w trwałym cache. Eksport ponownie zawierał 72 mecze, 17 kompletnych wyników
  i 9 drużyn; kopia dla aplikacji była identyczna bajtowo.
- Kopie dla aplikacji w `public/data/` były identyczne bajtowo z wyjściem importera.
  Skrót produkcyjnego `data/pomorska3liga.json` pozostał bez zmian: próby zapisywały
  dane do osobnych katalogów tymczasowych.

Początkowa próba Camoufox w tym środowisku zakończyła się błędem
`SEC_ERROR_UNKNOWN_ISSUER`. Powodem był brak zaufania do CA używanego tu proxy
HTTPS. Po imporcie zaufanego certyfikatu do prywatnego profilu Camoufox przez
`--camoufox-ca` import się powiódł. Weryfikacja TLS pozostała włączona.
Nie sklasyfikowano błędu certyfikatu jako blokady Cloudflare.

## Zakres dowodu

Próby wykonano w zarządzanym środowisku z proxy HTTPS kończącym TLS, nie na
komputerze użytkownika. Potwierdzają integrację i rzeczywisty odczyt danych;
nie dowodzą obejścia Cloudflare z dowolnego domowego adresu IP. W wymuszonym
teście przełączenia pierwszy silnik nie wystartował z powodu celowo błędnej
ścieżki przeglądarki, więc nie jest to pomiar reakcji na rzeczywiste 403.

Pełny import bez cache sprawdzono offline na HTML odtworzonym ze zweryfikowanego
snapshotu: 3 strony główne i 17 stron meczów. Rzeczywiste próby obejmowały
istniejący cache i pobieranie brakujących szczegółów.

Nie przeprowadzono wielodniowego pilotażu, próby wszystkich lig ani śledzenia LIVE.
Wyniki wcześniejszych prób na GitHub Actions znajdują się w
[raporcie porównawczym](https://github.com/midasracing/kiedysiatka/blob/experiment/volleystation-20261106/experiments/volleystation/report-community/RAPORT.md).

Pomiary i wyniki ostatnich uruchomień: [verification.json](verification.json).
Polecenia instalacji, pracy ciągłej i odczytu stanu: [README](README.md).

## Aktualizacja konfiguracji przy przejściu na domyślny importer

Historyczne pomiary powyżej poprzedzają kontrolę parametrów uruchamiania Chrome.
Przy konfiguracji proxy SeleniumBase dodawał własną flagę ignorowania błędów
certyfikatów. Domyślny importer przekazuje teraz proxy natywnie do Chrome
i jawnie włącza zabezpieczenia przeglądarki. Dwie równoległe sesje zweryfikowano
bez tych flag i z odrzuceniem niezaufanego certyfikatu. Osobne porty CDP usuwają
również konflikt przy jednoczesnym uruchamianiu obu lig. Aktualne wyniki zawiera
[raport przyjęcia wersji domyślnej](DOMYSLNY.md).
