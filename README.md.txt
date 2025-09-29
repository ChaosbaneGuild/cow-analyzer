# CoW Analyzer - Guild War Ranking Tool

Questo progetto serve ad analizzare i **log delle Clan War (CoW)** di Hero Wars e generare:

- Classifiche per attacco e difesa (eroi e titani)
- Punteggio totale della gilda per ogni guerra
- File Excel con riepilogo (`heroes.xlsx`, `titans.xlsx`, `season_summary_all.xlsx`)
- Una pagina HTML (in futuro) per condividere i ranking online

## ⚙️ Utilizzo

Mettere i file di log `.csv` (Attack Log e Defense Log) nella cartella del progetto e lanciare:

```bash
python cow_analyzer.py "08-09-2025*Attack Log.csv" "08-09-2025*Defense Log.csv"
