# Diagnostyka lig międzynarodowych

`probe_international_api.py` sprawdza publiczne źródła ligi włoskiej i japońskiej.
Opis wyników znajduje się w [INTERNATIONAL_AUDIT.md](INTERNATIONAL_AUDIT.md).

```bash
python -m pip install -r diagnostics/requirements.txt
python diagnostics/probe_international_api.py
```

Produkcyjny importer II i Pomorskiej III ligi oraz jego instrukcja znajdują się
w [`scripts/update_volleystation.py`](../scripts/update_volleystation.py) i
[instrukcji](../docs/volleystation.md).
