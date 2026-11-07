# Test pozyskiwania hal II ligi i Pomorskiej III ligi

**Odczytano i jednoznacznie dopasowano wszystkie 532 strony meczów II ligi.
PZPS publikuje lokalizację dla 531 spotkań, ale nazwę hali wraz z adresem tylko
przy 355. W publicznym bieżącym wykazie PWZPS dopasowano trzy spotkania Pomorskiej
III ligi z nazwą hali i adresem.**

To katalog testowy. Pliki `data/2liga.json` i `data/pomorska3liga.json` pozostają
bez zmian; ich pola `venue` nadal są puste. Nie zmieniano godzin ani wyników.

| Zakres | Mecze w feedzie | Sprawdzone szczegóły pasujące do meczu | Dowolna lokalizacja | Nazwa hali i adres | Samo miasto | Sprzeczne godziny |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| II liga, 5 grup | 532 | 532 | 531 | 355 | 28 | 1 |
| Pomorska III liga | 72 | 3 | 3 | 3 | 0 | 3 |

W II lidze **503 rekordy zawierają pole adresowe**: 355 także nazwę hali,
148 adres bez nazwy. Przy 28 meczach jest tylko miasto. Jeden mecz nie ma żadnej
lokalizacji: AKS V LO Rzeszów – KS Hutnik Kraków, 28.11.2026,
[szczegóły PZPS](https://sedziowie.pzps.pl/system/mecz/1107/).
**9 wpisów Wrześni wymienia halę dodatkową**; nie potwierdzono, w której z dwóch
hal odbędzie się konkretny mecz. Ta informacja pozostaje w `source_text` i
`alternatives_published=true`. Dziewięć wpisów jest częścią 355, nie dodatkowymi meczami.
Adresy zachowują tekst źródła; nie przeprowadzono geokodowania ani kontroli terenowej.

## Dopasowanie i jakość

Wszystkie 532 rekordy II ligi mają zgodny identyfikator VolleyStation osadzony
w widgetach PZPS. Dodatkowo sprawdzono dokładną datę, gospodarza i gościa,
grupę i numer meczu. Nie było niejednoznacznych dopasowań ani konfliktów ID.
Niezależny od parsera odczyt całego wiersza lokalizacji potwierdził brak utraty
tekstu we wszystkich 532 dokumentach, w tym alternatywnych hal.

Pomorska III liga wymaga jawnych aliasów nazw: KATS Alpat Gdynia →
KATS ALPAT CYMMAT GDYNIA; UKS Olimpijczyk Pruszcz Gd. → UKS Olimpijczyk Pruszcz
Gdański; Trefl Gdańsk → Energa Trefl Gdańsk III; LSZ Gniewkowo → LZS GNIEWKO
Gniewkowo. Aliasy są ograniczone do kategorii **III Liga Mężczyzn**, daty oraz
kierunku gospodarz–gość. Nie użyto dopasowywania po podobieństwie nazwy ani
przenoszenia domyślnej hali klubu na inne mecze. Każde użycie aliasu jest w raporcie.

Publiczny wykaz PWZPS pokazuje aktualnie opublikowane obsady. **69 pozostałych
spotkań III ligi nie uzyskało lokalizacji z tego odczytu**; nie oznacza to, że
lokalizacja nie istnieje w innych materiałach. Trzy dopasowania nie dowodzą
kompletności hal całego sezonu.

## Wykryte różnice godzin

| Mecz i data | VolleyStation / zapisany feed | PZPS lub PWZPS |
| --- | --- | --- |
| Stoczniowiec – Alpat, 07.11.2026 | 18:00 | 12:00 |
| Olimpijczyk Pruszcz Gd. – TELMAX Człuchów, 07.11.2026 | 18:00 | 14:00 |
| Trefl III – Gniewkowo, 08.11.2026 | 18:00 | 15:00 |
| BAS Białystok – Atak Elbląg, 14.11.2026 | 17:01 | 18:00 |

Trzy strony meczów III ligi pobrano ponownie: nadal pokazują 18:00, więc różnica
nie wynika jedynie ze starszej kopii naszego feedu. Strona BAS–Atak także nadal
pokazuje 17:01. Nie ustalono, który z rozbieżnych terminów jest wiążący.
Poprzedni audyt potwierdzał obecność godzin i zgodność z VolleyStation; ten test
ujawnił brak zgodności z drugim oficjalnym źródłem. Nie nadpisano tych wartości automatycznie.

## Dowody i powtórzenie

- [Raport maszynowy: 535 dopasowań, URL, czas, SHA-256, treść lokalizacji i konflikty](report.json)
- [Katalog testowy CSV](venues.csv)
- [Parser i kontrola dopasowań](../../../local_scraper/venue_audit.py)
- [Narzędzie przechwycenia publicznych stron](../../../local_scraper/capture_venues.py)

Źródła: [PZPS – indeks II ligi](https://sedziowie.pzps.pl/system/mecze-II-liga-mezczyzn/),
[PWZPS – publiczne delegacje](https://pwzps.arbitergo.pl/delegation/List.jsf).
Dostęp przez zwykłe HTTPS z weryfikacją TLS, bez logowania i płatnych usług.
Sprawdzono HTTP 200, brak challenge i skróty dokumentów. Odczyt całej II ligi
trwał około dziewięciu minut (07.11.2026, 13:05–13:14 UTC), sekwencyjnie z
odstępem co najmniej jednej sekundy; robots.txt PZPS nie określa Crawl-delay.
Dla VolleyStation zachowano odstęp co najmniej pięciu sekund. Surowe strony
pozostają w lokalnych artefaktach; nie eksportowano danych sędziów ani formularzy konta.

**11 testów regresji przeszło**, w tym odrzucanie złej daty, odwrotnego meczu,
niezgodnej grupy, numeru i ID; niewymyślanie nazwy hali z samego miasta;
zachowanie alternatywnych lokalizacji i zatrzymanie po HTTP 429.
Wznowienie przechwycenia sprawdzono na 537 zapisanych dokumentach przy wyłączonych
żądaniach sieciowych. Kontrola stylu Python przeszła.

```bash
python -m local_scraper.capture_venues --output .local-scraper/venue-captures
python -m local_scraper.venue_audit --captures .local-scraper/venue-captures --output .local-scraper/venue-report.json
python -m unittest discover -s tests -p 'test_venue_audit.py'
```

Pierwsza komenda może potrwać około dziesięciu minut. Zachowuje poprawne
przechwycenia przy przerwaniu i kończy pracę po odmowie źródła. Ponowne uruchomienie
z tym samym katalogiem wznawia zapis; do nowego odczytu źródeł należy użyć nowego
katalogu. Audyt wyjdzie z kodem 1, jeśli brakuje dopasowanych dokumentów II ligi.
Znacznik `complete_second_capture` oznacza komplet odczytów, nie kompletność metadanych hal.
