# Próby transportu VolleyStation

[Raport końcowy](report-final/RAPORT_KONCOWY.md) · [Tabela pomiarów CSV](report-final/wyniki.csv)

Izolowana kopia scrapera Pomorskiej III ligi: `scraper_copy.py`. Metadane źródła
znajdują się w `snapshot.json`. Kopia zapisuje wyłącznie do `outputs/`, nigdy do
produkcyjnego `data/`. Pozostałe scrapery i workflow nie są przełączane na te próby.

## Porównanie

`run.py` odpytuje kolejno terminarz, wyniki, tabelę Pomorskiej III ligi, listę drużyn
II ligi i jeden zakończony mecz. Wszystkie silniki używają tych samych parserów.
Wynik HTTP 200 bez poprawnych rekordów nie oznacza sukcesu.

Silniki: `requests`, Puppeteer + Stealth, Rebrowser Puppeteer i Patchright Python.
Przeglądarki korzystają z tego samego pliku wykonywalnego. Testujemy Stealth na
przypiętym Puppeteer 25.16.0; wcześniejsza wersja robocza produkcyjnego workflow
używa 24.31.0. To porównanie wariantów, nie odtworzenie całego runnera produkcyjnego.

Domyślnie dwie serie po pięć stron na silnik, bez automatycznych ponowień.
Odstęp co najmniej 3 s; po 401/403/429 lub nierozwiązanym challenge dany silnik
kończy próby. Kolejność silników jest obracana między seriami. W obrębie próby
każdy silnik zachowuje własną sesję. Nie współdzielimy cookies między silnikami.

```bash
python -m pip install -r experiments/volleystation/requirements.txt
PUPPETEER_SKIP_DOWNLOAD=true npm ci --prefix experiments/volleystation
LAB_BROWSER=/usr/bin/chromium python experiments/volleystation/run.py
```

Jeśli środowisko wymaga wyłączonego sandboxa Chromium, dodaj
`LAB_NO_SANDBOX=true`. Domyślnie sandbox pozostaje włączony. `LAB_HEADFUL=true`
wymaga działającego serwera X i pozwala uruchomić dodatkową serię z interfejsem.

W zarządzanym środowisku odziedziczony `HTTPS_PROXY` jest używany również przez
przeglądarki (można jawnie ustawić `LAB_PROXY`). Zaufany certyfikat CA tego proxy
musi być zainstalowany w magazynie Chromium. Nie wyłączamy walidacji TLS.
Nie umieszczaj danych uwierzytelniających proxy w adresie `LAB_PROXY`.
Jeśli proxy kończy połączenia TLS, zewnętrzny serwer widzi parametry TLS proxy,
nie przeglądarki. Takiej próby nie należy traktować jako porównania fingerprintów
TLS bezpośrednich połączeń z VolleyStation.

`results.jsonl` zawiera statusy, czasy, tytuły, liczbę rekordów, identyfikatory
Cloudflare Ray i skróty danych. Nie zapisuje cookies ani pełnego HTML.
`results.meta.json` zawiera konfigurację i wersje. Profile są tymczasowe i są
usuwane po zakończeniu procesu. Pierwszy odczyt przeglądarki obejmuje czas startu.

```bash
python experiments/volleystation/report.py
```

Pełny import kopii scrapera (maksymalnie 40 żądań, po 3 s odstępu) można
uruchomić niezależnie:

```bash
python experiments/volleystation/full_scrape.py --engine http
```

Wynik trafia do `outputs/http/pomorska3liga.json`, a podsumowanie do
`outputs/http/summary.json`. Program sprawdza skrót produkcyjnego feedu przed
i po próbie. Dla innych silników zmień `--engine`.

Osobny workflow `.github/workflows/experiment-volleystation.yml` jest uruchamiany
wyłącznie ręcznie. Testuje silniki kolejno na GitHub Actions i udostępnia pomiary
jako artefakty; nie zapisuje ani nie publikuje feedów. Samo dodanie pliku lokalnie
nie uruchamia tego workflow na GitHubie.

Pojedynczy adres sieciowy i krótka seria nie wystarczą do oceny długoterminowej
niezawodności. Jeśli żaden silnik nie napotka challenge, test potwierdza odczyt
danych, lecz nie skuteczność obchodzenia Cloudflare. Nie odtwarza także warunków
sieciowych GitHub Actions.

Na gałęzi `experiment/volleystation-20261106` workflow uruchamia się po zmianie
plików eksperymentu. Obejmuje headless z restartem procesów i zachowanym profilem
oraz headful przez Xvfb. Uprawnienia workflow to wyłącznie odczyt repozytorium.
