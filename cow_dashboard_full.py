# cow_dashboard_full.py
# Streamlit dashboard per Clash of Worlds logs (Attack + Defense)
# Requisiti: streamlit, pandas, openpyxl
# pip install streamlit pandas openpyxl

import streamlit as st
import pandas as pd
import re
import os
import json
from io import BytesIO
from pathlib import Path
from datetime import datetime

st.set_page_config(page_title="CoW Analyzer Dashboard", layout="wide")

# =========================
# Config utente (modifica qui se necessario)
# =========================
GUILD_MEMBERS = {
    "LOKI","LoveBigFeet","Frodo","H4V0C","Wadjet..","HAI","Nemo","CKG","yoyo",
    "Barah","FakeTaxi","georgesantos","Mokree","Masterlynch","DLGS","XungCa",
    "BuzzKill","Obi-Wan Kenobi","DrStein","Samujas","Pelarian Jauh","ElenDil",
    "kaliber 44","Biff","Pepp","Avalon"
}

HERO_FORTS = {
    "Barracks","Mage Academy","Lighthouse","Foundry","Engineerium","Shooting Range",
    "Bastion","Heroes' Bridge","Alchemy Tower","City Hall","Citadel"
}

TITAN_FORTS = {
    "Bridge","Spring of Elements","Bastion of Fire","Gates of Nature","Bastion of Ice",
    "Altar of Life","Ether Prism","Sun Temple","Moon Temple"
}



# Normalized guild members set and ignore pattern for defense parsing

# Normalized guild members set and ignore pattern for defense parsing
GUILD_MEMBERS_NORM = {g.strip().lower() for g in {
    "loki","lovebigfeet","frodo","h4v0c","wadjet..","hai","nemo","ckg","yoyo",
    "barah","faketaxi","georgesantos","mokree","masterlynch","dlgs","xungca",
    "buzzkill","obi-wan kenobi","drstein","samujas","pelarian jauh","elendil",
    "kaliber 44","biff","pepp","avalon"
}}

_IGNORE_RE = re.compile(
    r"(skill|cooldown|decrease|increase|bonus|fortification|captured|victory|defeat|points|\+|attack|defense|buff|resist|reduction|chance|critical|stun|heal|regen|immunity)",
    flags=re.IGNORECASE
)

def parse_defense_bytes_strict(bytes_io):
    """Strict defense parser: only accept defenders that match guild members (normalized).
    Returns DataFrame with columns Fortification, BaseFort, Defender, Type"""
    text = bytes_io.getvalue().decode(errors="ignore").splitlines()
    rows = []
    hero_set = set(f.lower() for f in HERO_FORTS)
    titan_set = set(f.lower() for f in TITAN_FORTS)
    for line in text:
        cols = [c.strip() for c in line.split(",")]
        if len(cols) < 2:
            continue
        fort = cols[0]
        result = cols[1].lower()
        base_fort = re.sub(r"\s*\(.*?\)", "", fort).strip().lower()
        defender = None
        for cand in reversed(cols):
            cand_clean = re.sub(r"\s*\(.*?\)", "", cand).strip()
            if not cand_clean:
                continue
            cand_norm = cand_clean.lower()
            # direct membership
            if cand_norm in GUILD_MEMBERS_NORM:
                defender = cand_clean
                break
            # alphanumeric normalization match
            cand_alnum = re.sub(r'[^a-z0-9]','', cand_norm)
            if cand_alnum and any(re.sub(r'[^a-z0-9]','',gm)==cand_alnum for gm in GUILD_MEMBERS_NORM):
                defender = cand_clean
                break
            # skip buff/label-like candidates
            if _IGNORE_RE.search(cand_clean):
                continue
            # otherwise skip
            continue
        if defender and result == "defeat":
            if base_fort in hero_set:
                btype = "Heroes"
            elif base_fort in titan_set:
                btype = "Titans"
            else:
                btype = "Unknown"
            rows.append({"Fortification": fort, "BaseFort": base_fort, "Defender": defender, "Type": btype})
    import pandas as pd
    if not rows:
        return pd.DataFrame(columns=["Fortification","BaseFort","Defender","Type"])
    return pd.DataFrame(rows)


LOGS_DIR = Path("logs")             # dove salviamo i CSV caricati
SEASON_FILE = Path("season_scores.json")
OUTPUT_HEROES = Path("heroes.xlsx")
OUTPUT_TITANS = Path("titans.xlsx")

# Crea cartella logs se non esiste
LOGS_DIR.mkdir(exist_ok=True)

# =========================
# Funzioni di parsing (stessa logica usata)
# =========================
def _clean_base_fort(name):
    return re.sub(r"\s*\(.*?\)","", name).strip().lower()

def parse_attack_bytes(bytes_io):
    # bytes_io: file caricato (io.BytesIO)
    battles = []
    bonuses = {}
    text = bytes_io.getvalue().decode(errors="ignore").splitlines()
    for line in text:
        row = [x.strip() for x in line.split(",")]
        if len(row) >= 4 and row[1] in ("Victory","Defeat") and row[2].startswith("+"):
            fort_display = row[0]
            base_fort = _clean_base_fort(fort_display)
            result = row[1]
            try:
                points = float(row[2].replace("+",""))
            except:
                points = 0.0
            attacker = re.sub(r"\s*\(.*?\)","",row[3]).strip()
            if attacker in GUILD_MEMBERS:
                battles.append({
                    "Fortification": fort_display,
                    "BaseFort": base_fort,
                    "Attacker": attacker,
                    "Result": result,
                    "Points": points
                })
        elif len(row) >= 3 and row[1] == "Fortification captured" and row[2].startswith("+"):
            base_fort = _clean_base_fort(row[0])
            try:
                bonus = float(row[2].replace("+",""))
            except:
                bonus = 0.0
            bonuses[base_fort] = bonuses.get(base_fort,0)+bonus

    df = pd.DataFrame(battles)
    if df.empty:
        return df

    df["Type"] = df["BaseFort"].apply(lambda x: "Heroes" if x in set(f.lower() for f in HERO_FORTS) else "Titans")
    # distribuzione bonus
    bonus_rows = []
    for base_fort, bonus in bonuses.items():
        winners = df[(df["BaseFort"]==base_fort)&(df["Result"]=="Victory")]
        if len(winners)>0 and bonus>0:
            quota = bonus/len(winners)
            for _, row in winners.iterrows():
                bonus_rows.append({
                    "Fortification": row["Fortification"],
                    "BaseFort": base_fort,
                    "Attacker": row["Attacker"],
                    "Result": "Bonus",
                    "Points": quota,
                    "Type": row["Type"]
                })
    if bonus_rows:
        df = pd.concat([df, pd.DataFrame(bonus_rows)], ignore_index=True)

    return df

def parse_defense_bytes(bytes_io):
    # wrapper to call strict parser
    return parse_defense_bytes_strict(bytes_io)

# =========================
# Utility season file
# =========================
def load_season():
    if SEASON_FILE.exists():
        return json.loads(SEASON_FILE.read_text(encoding="utf-8"))
    return {"heroes_attack":{}, "titans_attack":{}, "heroes_defense":{}, "titans_defense":{}}

def save_season(season):
    SEASON_FILE.write_text(json.dumps(season, indent=2), encoding="utf-8")

# =========================
# UI Streamlit
# =========================
st.title("⚔️ Clash of Worlds — Dashboard")

st.sidebar.header("Operazioni rapide")
mode = st.sidebar.radio("Scegli:", ["Upload CSV", "Scansiona cartella logs", "Visualizza stagionale", "Impostazioni"])

if mode == "Upload CSV":
    st.info("Carica qui i log (Attack e/o Defense). I file saranno salvati nella cartella logs/ e processati.")
    uploaded = st.file_uploader("Seleziona file CSV (più file accettati)", type="csv", accept_multiple_files=True)
    if uploaded:
        st.success(f"{len(uploaded)} file caricati; salvataggio in logs/")
        processed = []
        for f in uploaded:
            # salva su disco
            safe_name = f.name
            out_path = LOGS_DIR / safe_name
            out_path.write_bytes(f.getvalue())
            processed.append(safe_name)
        st.write("File salvati:", processed)
        try:
            if hasattr(st, "experimental_rerun"):
                st.experimental_rerun()
            else:
                raise AttributeError
        except Exception:
            st.info(
                "I file sono stati salvati nella cartella logs/. "
                "Ricarica manualmente la pagina (F5) per visualizzare i file salvati, "
                "oppure vai su 'Scansiona cartella logs' e premi 'Processa selezionati'."
            )
elif mode == "Scansiona cartella logs":
    st.info(f"Cartella di scansione: {LOGS_DIR.resolve()}")
    files = sorted([p for p in LOGS_DIR.glob("*.csv")])
    if not files:
        st.warning("Nessun CSV nella cartella logs/. Carica dei file o usa Upload CSV.")
    else:
        selected = st.multiselect("Scegli i log da processare (in ordine):", [str(p.name) for p in files], default=[str(p.name) for p in files])
        if st.button("Processa selezionati"):
            season = load_season()
            per_date = {}
            for fname in selected:
                fpath = LOGS_DIR / fname
                # Determina tipo dal nome del file
                low = fname.lower()
                if "attack log" in low:
                    with fpath.open("rb") as fh:
                        df_a = parse_attack_bytes(BytesIO(fh.read()))
                    df_d = None
                elif "defense log" in low:
                    with fpath.open("rb") as fh:
                        df_d = parse_defense_bytes(BytesIO(fh.read()))
                    df_a = None
                else:
                    st.error(f"Impossibile determinare tipo per: {fname} (usa 'Attack Log' o 'Defense Log' nel nome)")
                    continue

                key = fname
                per_date[key] = {"attack": df_a if df_a is not None else pd.DataFrame(), "defense": df_d if df_d is not None else pd.DataFrame()}

                # update season
                if df_a is not None and not df_a.empty:
                    for t in ["Heroes","Titans"]:
                        sub = df_a[df_a["Type"]==t].groupby("Attacker")["Points"].sum()
                        skey = f"{t.lower()}_attack"
                        for player, pts in sub.items():
                            season[skey][player] = season[skey].get(player,0)+float(pts)
                if df_d is not None and not df_d.empty:
                    for t in ["Heroes","Titans"]:
                        sub = df_d[df_d["Type"]==t]["Defender"].value_counts()
                        skey = f"{t.lower()}_defense"
                        if skey not in season:
                            season[skey] = {}
                        for player, cnt in sub.items():
                            season[skey][player] = season[skey].get(player,0)+int(cnt)

            save_season(season)

            # mostra risultati per ogni file processato
            for name, data in per_date.items():
                st.subheader(f"Log: {name}")
                if not data["attack"].empty:
                    st.write("Attacco - Eroi")
                    st.dataframe(data["attack"][data["attack"]["Type"]=="Heroes"].groupby("Attacker")["Points"].sum().reset_index().sort_values("Points",ascending=False))
                    st.write("Attacco - Titani")
                    st.dataframe(data["attack"][data["attack"]["Type"]=="Titans"].groupby("Attacker")["Points"].sum().reset_index().sort_values("Points",ascending=False))
                if not data["defense"].empty:
                    st.write("Difesa - Eroi")
                    st.dataframe(data["defense"][data["defense"]["Type"]=="Heroes"]["Defender"].value_counts().reset_index().rename(columns={"index":"Defender","Defender":"Count"}))
                    st.write("Difesa - Titani")
                    st.dataframe(data["defense"][data["defense"]["Type"]=="Titans"]["Defender"].value_counts().reset_index().rename(columns={"index":"Defender","Defender":"Count"}))

            st.success("Processamento completato e season_scores.json aggiornato.")
            try:
                if hasattr(st, "experimental_rerun"):
                    st.experimental_rerun()
                else:
                    raise AttributeError
            except Exception:
                st.info(
                    "I file sono stati salvati nella cartella logs/. "
                    "Ricarica manualmente la pagina (F5) per visualizzare i file salvati, "
                    "oppure vai su 'Scansiona cartella logs' e premi 'Processa selezionati'."
                )
elif mode == "Visualizza stagionale":
    season = load_season()
    st.header("Classifiche stagionali (cumulative)")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Attacco - Eroi")
        df_ha = pd.DataFrame(list(season.get("heroes_attack",{}).items()), columns=["Attacker","Points"]).sort_values("Points",ascending=False)
        st.dataframe(df_ha)
        st.subheader("Difesa - Eroi (conteggi)")
        df_hd = pd.DataFrame(list(season.get("heroes_defense",{}).items()), columns=["Defender","Count"]).sort_values("Count",ascending=False)
        st.dataframe(df_hd)
    with col2:
        st.subheader("Attacco - Titani")
        df_ta = pd.DataFrame(list(season.get("titans_attack",{}).items()), columns=["Attacker","Points"]).sort_values("Points",ascending=False)
        st.dataframe(df_ta)
        st.subheader("Difesa - Titani (conteggi)")
        df_td = pd.DataFrame(list(season.get("titans_defense",{}).items()), columns=["Defender","Count"]).sort_values("Count",ascending=False)
        st.dataframe(df_td)

    st.markdown("---")
    if st.button("Scarica season_scores.json"):
        st.download_button("Download JSON", data=json.dumps(season,indent=2), file_name="season_scores.json", mime="application/json")

    if st.button("Esporta Excel stagionale (heroes/titans)"):
        # crea un excel in memoria con fogli
        with BytesIO() as bio:
            with pd.ExcelWriter(bio, engine="openpyxl") as writer:
                df_ha.to_excel(writer, sheet_name="Heroes_Attack_Season", index=False)
                df_hd.to_excel(writer, sheet_name="Heroes_Defense_Season", index=False)
                df_ta.to_excel(writer, sheet_name="Titans_Attack_Season", index=False)
                df_td.to_excel(writer, sheet_name="Titans_Defense_Season", index=False)
            bio.seek(0)
            st.download_button("Scarica Excel stagionale", data=bio.read(), file_name="season_summary.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

else:
    st.write("Vai nella barra laterale e scegli un'azione.")

# Footer
st.markdown("---")
st.caption("Nota: Se desideri esporre l'app su internet, usa un servizio di hosting o ngrok; proteggi l'endpoint prima di condividerlo pubblicamente.")
