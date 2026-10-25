# VOLLEY HUB

Mobilna aplikacja webowa/PWA do śledzenia siatkówki. To pierwsza wersja: interfejs, nawigacja, kalendarz, wyszukiwarka i ulubione działają lokalnie w przeglądarce.

## Publikacja przez GitHub Pages
1. W repozytorium wejdź w **Settings → Pages**.
2. Wybierz **Deploy from a branch**, branch `main`, folder `/(root)`, kliknij **Save**.
3. Po wdrożeniu adres powinien być: `https://midasracing.github.io/Volley-hub/`.

## Ważne
- Terminarze i wyniki nie są jeszcze podłączone; aplikacja nie pokazuje fikcyjnych wyników.
- Jedyne preferowane źródło dla Pomorskiej III Ligi Męskiej: [VolleyStation](https://pomorskie.volleystation.com/pl/phase-6796-pomorska-iii-liga-meska/schedule/). Przed integracją trzeba sprawdzić stabilność dostępu i warunki użycia.
- Ulubione zapisują się lokalnie w przeglądarce.
- PWA może być dodana do ekranu początkowego; powiadomienia push wymagają dodatkowej infrastruktury.
- Widżety systemowe i Live Activities na iOS wymagają aplikacji natywnej.

## Następne kroki
1. Zweryfikować stabilne źródła terminarzy dla poszczególnych lig.
2. Zintegrować VolleyStation jako jedyne źródło dla wskazanej Pomorskiej III Ligi Męskiej.
3. Dodać automatyczne aktualizacje danych i strony szczegółów meczu.