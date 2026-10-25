# VOLLEY HUB

**VOLLEY HUB** to mobilne centrum informacji o siatkówce. Celem aplikacji jest zebranie w jednym miejscu terminarzy, wyników i informacji o rozgrywkach, aby łatwo sprawdzić, kto gra, kiedy odbywa się mecz i jak zakończyło się spotkanie. Projekt jest rozwijany przede wszystkim z myślą o wygodnym korzystaniu na telefonie.

## Co ma oferować aplikacja

- **Główna** — szybki podgląd najważniejszych meczów i wydarzeń.
- **Mecze** — przegląd spotkań z możliwością wyszukiwania oraz filtrowania według daty i statusu.
- **Rozgrywki** — dostęp do lig i turniejów.
- **Ulubione** — szybki dostęp do wybranych drużyn i rozgrywek.
- **Wyszukiwarka** — odnajdywanie interesujących meczów, zespołów i rozgrywek.

Interfejs jest przygotowywany jako aplikacja webowa typu PWA, dzięki czemu można korzystać z niego w przeglądarce i dodać go do ekranu początkowego telefonu.

## Skąd pochodzą informacje

Rzetelność danych jest ważniejsza niż pokazywanie niezweryfikowanych wyników. Informacje o meczach powinny pochodzić ze sprawdzonych źródeł organizatorów rozgrywek lub oficjalnych systemów wynikowych.

### Pomorska III Liga Męska

Dla Pomorskiej III Ligi Męskiej jedynym źródłem danych jest **VolleyStation** — zgodnie z założeniami projektu nie należy uzupełniać tej ligi informacjami z innych serwisów.

- Terminarz: https://pomorskie.volleystation.com/pl/phase-6796-pomorska-iii-liga-meska/schedule/

Zakres rozgrywek obejmuje zespoły z województw pomorskiego i kujawsko-pomorskiego. Przed automatycznym pobieraniem danych należy sprawdzić dostępność źródła oraz warunki jego wykorzystania.

### Pozostałe ligi i turnieje

Źródła dla pozostałych rozgrywek wymagają osobnej weryfikacji. Nie należy zakładać, że dane są już zintegrowane, ani prezentować fikcyjnych terminarzy czy wyników. Przy każdej integracji trzeba ustalić źródło i sprawdzić, czy dostarcza aktualne informacje.

## Aktualny stan projektu

Na obecnym etapie repozytorium zawiera interfejs aplikacji i podstawową obsługę nawigacji, wyszukiwania oraz ulubionych zapisywanych lokalnie w przeglądarce. **Terminarze i wyniki nie są jeszcze podłączone do źródeł danych**, dlatego aplikacja nie powinna być traktowana jako aktualny serwis wynikowy.

## Uruchomienie przez GitHub Pages

1. Otwórz **Settings → Pages** w ustawieniach repozytorium.
2. Wybierz **Deploy from a branch**.
3. Ustaw branch `main` i folder `/(root)`, a następnie kliknij **Save**.
4. Po zakończeniu wdrożenia aplikacja powinna być dostępna pod adresem: https://midasracing.github.io/Volley-hub/

## Dalszy rozwój

Kolejne etapy to podłączenie zweryfikowanych źródeł danych, rozpoczęcie integracji Pomorskiej III Ligi Męskiej wyłącznie z VolleyStation oraz dodanie szczegółów spotkań i aktualizacji wyników.
