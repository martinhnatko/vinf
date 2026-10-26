# Vyhľadávanie filmov na Rotten Tomatoes

Projekt na predmet VINF: vlastný crawler, extractor, invertovaný index s raw TF a konzolové vyhľadávanie nad názvami a synopsami filmov. Searcher podporuje dve IDF metódy a tri spôsoby skórovania.

## Požiadavky

- Git a Python 3.

## Klonovanie a spustenie

```bash
git clone https://github.com/martinhnatko/vinf.git
cd vinf
python3 app/crawler.py
python3 app/extractor.py
python3 app/indexer.py
python3 app/searcher.py
```

| Skript | Úloha a výstup |
| --- | --- |
| `crawler.py` | Stiahne HTML stránky do `app/data/raw/`. |
| `extractor.py` | Spracuje HTML, odstráni duplicity a zapíše `app/data/movies.jsonl`. |
| `indexer.py` | Vytvorí invertovaný index v `app/data/index.json`. |
| `searcher.py` | Spustí interaktívne vyhľadávanie nad dokumentmi a indexom. |

Pôvodný zber dát trval približne 16 hodín.

Konfigurácia je v [`app/config.json`](app/config.json). Cesty k dátam sa vyhodnocujú vzhľadom na adresár tohto súboru. Výstupné adresáre vytvárajú skripty automaticky.

## Vyhľadávanie nad priloženými dátami

Repozitár obsahuje `app/data/movies.jsonl` aj `app/data/index.json`. Po naklonovaní repozitára preto na vyskúšanie vyhľadávania stačí:

```bash
python3 app/searcher.py
```

Surové HTML nie sú súčasťou repozitára. Pri obnove dát najprv spustite crawler; extractor a indexer prepíšu existujúce dátové súbory.