# Allsvenskan Analytics 🔵⚪
**IFK Göteborg fokus · FBRef data · Streamlit**

En interaktiv fotbollsanalys-app för Allsvenskan med djupanalys av IFK Göteborg.

## Vyer
- **⊞ IFK Göteborg** — lagsummering, spelarprofiler, Scout Lab-statistik
- **☰ Alla spelare** — sorteringsbar tabell för hela ligan
- **⇄ Jämför spelare** — radardiagram + percentiltabell upp till 4 spelare
- **◫ Lagöversikt** — alla 16 lag med visualiseringar
- **🌍 Nationaliteter** — spelarnas ursprungsländer med säsongsjämförelse
- **🔍 Transferscout** — hitta statistiskt liknande spelare (cosine similarity)
- **📈 Spelarutveckling** — följ en spelare 2022→2023→2025
- **📅 Säsongsöversikt** — match-för-match tidslinje + spelarbidrag
- **⭐ Nästa Steg** — auto-scout av unga talanger (A+→C betyg)
- **📄 Scouting Report** — exporterbar PNG per spelare

## Köra lokalt

```bash
pip install -r requirements.txt
python process_data.py   # generera data.json från xlsx-filer
streamlit run app.py
```

## Datastruktur
```
blavitttest/
├── app.py
├── process_data.py
├── fbref_updater.py
├── requirements.txt
├── data.json              # genereras av process_data.py
├── match_data_2025.json   # matchlogg IFK Göteborg 2025
├── match_data_2024.json   # matchlogg IFK Göteborg 2024
└── 90minutersdata/        # xlsx-filer från FBRef (ej i git)
    ├── Player/
    ├── Squad/
    ├── Match Logs IFK Göteborg/
    └── *_Allsvenskan_Nationalities.xlsx
```

## Deploy till Streamlit Cloud

1. Pusha repot till GitHub (privat repo fungerar)
2. Gå till [share.streamlit.io](https://share.streamlit.io)
3. Koppla GitHub-konto → välj repo → `app.py`
4. Klicka **Deploy**

`data.json` och `match_data_*.json` måste vara committade i repot
(de genereras lokalt och pushas upp).

## Auto-uppdatering (lokal)
```bash
python fbref_updater.py --season 2025
```
Task Scheduler: Måndag 23:00 + Tisdag 08:00

## Data
Statistik från [FBRef.com](https://fbref.com) · Allsvenskan comp ID: 29
Säsonger: 2001, 2022, 2023, 2025
"# 90mindata" 
