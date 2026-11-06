# Rozszerzona seria prób

Cel: sprawdzić powtarzalność i dostęp po zmianie stanu sesji. Pojedynczy udany
import nie jest dowodem stabilności.

| Scenariusz | Zmieniana właściwość |
| --- | --- |
| cam-live | Jedna działająca przeglądarka, do 3 kolejnych aktualizacji |
| cam-linux | Fingerprint ograniczony do Linuxa zgodnego z hostem |
| cam-cache | Linux i włączony cache przeglądarki |
| cam-fresh | Nowy profil i fingerprint przed kolejną aktualizacją |
| cam-restart | Restart z tym samym profilem i konfiguracją; jedna próba odzyskania dostępu po 60 s, jeśli wystąpi blokada |
| cam-recorded | Profil rzeczywistego urządzenia z zestawu Camoufox |
| cam-handoff | Przekazanie sesji do curl_cffi z profilem Firefox, bez zapisywania cookies w artefaktach |
| nodriver-headless / nodriver-headful | Chrome sterowany przez NoDriver, bez Puppeteera |
| stock-firefox | Zwykły Firefox Playwright, bez Camoufox |
| curl-profiles | TLS/HTTP Chrome, Firefox i Safari |

Każde zadanie zaczyna się od kontrolnego odczytu przez `requests`. Scenariusze
działają na niezależnych runnerach; równolegle wykonujemy najwyżej dwa. To ogranicza
możliwość przypisywania różnic wyłącznie bibliotece, ponieważ zmieniają się też IP.

Importy przyrostowe zaczynają od istniejącego feedu i używają kolejnej wersji jako
cache tylko po przejściu kontroli kompletności. Odstęp między nawigacjami wynosi
co najmniej 8 s, między aktualizacjami 20 s. Po odmowie dostępu scenariusz kończy
odczyty; wyjątkiem jest jedna jawna próba po 60 s w scenariuszu odzyskiwania sesji.

Limit: 14 nawigacji na scenariusz Camoufox, 3 na pozostały scenariusz, plus jeden
kontrolny odczyt HTTP na zadanie. Limity dotyczą dokumentów, nie zasobów strony.
Interaktywnych CAPTCHA nie rozwiązujemy automatycznie. Nie kupujemy usług proxy
ani zewnętrznych solverów.

Artefakty zawierają statusy, wyniki parsera, kontrolę kompletności, skróty konfiguracji
fingerprintu i ostatni poprawny eksport. Nie zawierają profili przeglądarki,
wartości cookies ani zrzutu środowiska. Produkcyjny feed pozostaje bez zmian.
