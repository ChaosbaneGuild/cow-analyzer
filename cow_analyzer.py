#!/usr/bin/env python3
"""
cow_analyzer.py
Parse Clash of Worlds logs (Attack / Defense), compute per-war and season leaderboards,
distribute fortification bonuses among winners, and export Excel + season JSON.

Usage:
    python cow_analyzer.py "04-09-2025*Attack Log.csv" "04-09-2025*Defense Log.csv" ...
    python cow_analyzer.py ./*.csv
If no arguments are given, the script will process all "*.csv" in the current folder.
"""

import sys
import argparse
from pathlib import Path
import re
import json
from io import StringIO
import pandas as pd

# -------- CONFIG: adjust guild members & fort lists here if needed ----------
GUILD_MEMBERS = {
    "LOKI","LoveBigFeet","Frodo","H4V0C","Wadjet..","HAI","Nemo","CKG","yoyo",
    "Barah","FakeTaxi","georgesantos","Mokree","Masterlynch","DLGS","XungCa",
    "BuzzKill","Obi-Wan Kenobi","DrStein","Samujas","Pelarian Jauh","ElenDil",
    "kaliber 44","Biff","Pepp","Avalon"
}
GUILD_NORM = {g.strip().lower() for g in GUILD_MEMBERS}

HERO_FORTS = {"Barracks","Mage Academy","Lighthouse","Foundry","Engineerium","Shooting Range",
    "Bastion","Heroes' Bridge","Alchemy Tower","City Hall","Citadel"}
TITAN_FORTS = {"Bridge","Spring of Elements","Bastion of Fire","Gates of Nature","Bastion of Ice",
    "Altar of Life","Ether Prism","Sun Temple","Moon Temple"}
HERO_SET = set(f.lower() for f in HERO_FORTS)
TITAN_SET = set(f.lower() for f in TITAN_FORTS)

# Patterns to ignore as "defender candidate" (buff labels, UI text)
_IGNORE_RE = re.compile(
    r"(skill|cooldown|decrease|increase|bonus|fortification|captured|victory|defeat|points|\+|attack|defense|buff|resist|reduction|chance|critical|stun|heal|regen|immunity)",
    flags=re.IGNORECASE
)

# Season file output
SEASON_FILE = Path("season_scores.json")

# ----------------- utility functions -----------------
def _clean_base_fort(name):
    """Remove parentheses and whitespace, lowercased base fort name (used to decide Heroes/Titans)"""
    return re.sub(r"\s*\(.*?\)","", str(name)).strip().lower()

def parse_attack_text(text):
    """
    Parse an attack log text (CSV-like).
    Returns a DataFrame with columns:
      Fortification, BaseFort, Attacker, Result, Points, Type
    Also includes additional rows with Result == "Bonus" representing distributed bonus shares.
    """
    rows = []
    bonuses = {}  # base_fort -> total bonus to distribute
    for line in text.splitlines():
        cols = [c.strip() for c in line.split(",")]
        if len(cols) >= 4 and cols[1] in ("Victory","Defeat") and cols[2].startswith("+"):
            fort_display = cols[0]
            base_fort = _clean_base_fort(fort_display)
            result = cols[1]
            try:
                pts = float(cols[2].replace("+",""))
            except:
                pts = 0.0
            attacker = re.sub(r"\s*\(.*?\)","", cols[3]).strip()
            rows.append({
                "Fortification": fort_display,
                "BaseFort": base_fort,
                "Attacker": attacker,
                "Result": result,
                "Points": pts
            })
        # Fortification captured +XXX lines
        elif len(cols) >= 3 and cols[1] == "Fortification captured" and cols[2].startswith("+"):
            base = _clean_base_fort(cols[0])
            try:
                bonus = float(cols[2].replace("+",""))
            except:
                bonus = 0.0
            bonuses[base] = bonuses.get(base, 0.0) + bonus

    if not rows:
        return pd.DataFrame(columns=["Fortification","BaseFort","Attacker","Result","Points","Type"])

    df = pd.DataFrame(rows)
    df["Type"] = df["BaseFort"].apply(lambda x: "Heroes" if x in HERO_SET else ("Titans" if x in TITAN_SET else "Unknown"))

    # Distribute bonuses: for each base fort, find all winning attack occurrences and give each occurrence a share.
    bonus_rows = []
    for base, total_bonus in bonuses.items():
        winners = df[(df["BaseFort"]==base) & (df["Result"]=="Victory")]
        if len(winners) > 0 and total_bonus > 0:
            share = total_bonus / len(winners)
            # create one Bonus row per winning occurrence
            for _, wr in winners.iterrows():
                bonus_rows.append({
                    "Fortification": wr["Fortification"],
                    "BaseFort": base,
                    "Attacker": wr["Attacker"],
                    "Result": "Bonus",
                    "Points": share,
                    "Type": wr["Type"]
                })
    if bonus_rows:
        df = pd.concat([df, pd.DataFrame(bonus_rows)], ignore_index=True)

    return df

def parse_defense_text_strict(text):
    """
    Strict defense parser: accepts as defender only names that match GUILD_NORM (or close alnum match).
    Returns DataFrame with columns: Fortification, BaseFort, Defender, Type
    We consider a defense successful when the log line's second column is 'Defeat' (attacker defeated).
    """
    rows = []
    for line in text.splitlines():
        cols = [c.strip() for c in line.split(",")]
        if len(cols) < 2:
            continue
        fort = cols[0]
        result = cols[1].lower()
        base = _clean_base_fort(fort)
        defender = None
        # scan from end to start for the likely defender name
        for cand in reversed(cols):
            cclean = re.sub(r"\s*\(.*?\)","", cand).strip()
            if not cclean:
                continue
            cnorm = cclean.lower()
            if cnorm in GUILD_NORM:
                defender = cclean
                break
            # alphanumeric approximate match
            cand_alnum = re.sub(r'[^a-z0-9]','', cnorm)
            if cand_alnum and any(re.sub(r'[^a-z0-9]','',g)==cand_alnum for g in GUILD_NORM):
                defender = cclean
                break
            # skip buff/labels
            if _IGNORE_RE.search(cclean):
                continue
            # otherwise not a player name -> continue searching
        if defender and result == "defeat":
            if base in HERO_SET:
                btype = "Heroes"
            elif base in TITAN_SET:
                btype = "Titans"
            else:
                btype = "Unknown"
            rows.append({
                "Fortification": fort,
                "BaseFort": base,
                "Defender": defender,
                "Type": btype
            })
    if not rows:
        return pd.DataFrame(columns=["Fortification","BaseFort","Defender","Type"])
    return pd.DataFrame(rows)

# ----------------- season helpers -----------------
def load_season():
    if SEASON_FILE.exists():
        try:
            return json.loads(SEASON_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"heroes_attack":{}, "titans_attack":{}, "heroes_defense":{}, "titans_defense":{}}
    return {"heroes_attack":{}, "titans_attack":{}, "heroes_defense":{}, "titans_defense":{}}

def save_season(season):
    SEASON_FILE.write_text(json.dumps(season, indent=2), encoding="utf-8")

# ----------------- main processing -----------------
def main(argv):
    parser = argparse.ArgumentParser(description="Process CoW logs and generate ranking files")
    parser.add_argument("files", nargs="*", help="CSV log files (globs allowed). If none, all *.csv in cwd are processed.")
    parser.add_argument("--no-save-season", action="store_true", help="Do not update season_scores.json")
    args = parser.parse_args(argv)

    # resolve input files
    files = []
    if not args.files:
        files = sorted(Path(".").glob("*.csv"))
    else:
        for pattern in args.files:
            files.extend(sorted(Path(".").glob(pattern)))
    files = [p for p in files if p.is_file()]
    if not files:
        print("No CSV files found to process.")
        return 1

    # group files by date prefix (dd-mm-yyyy) if present, else by filename
    groups = {}
    for p in files:
        m = re.match(r"(\d{2}-\d{2}-\d{4})", p.name)
        key = m.group(1) if m else p.name
        groups.setdefault(key, {"attack": None, "defense": None, "attack_path": None, "defense_path": None})
        if "attack log" in p.name.lower():
            groups[key]["attack"] = p
            groups[key]["attack_path"] = p.name
        if "defense log" in p.name.lower():
            groups[key]["defense"] = p
            groups[key]["defense_path"] = p.name
    # process each group
    season = load_season()
    per_war = {}
    for key, info in sorted(groups.items(), key=lambda x: x[0]):
        attack_df = pd.DataFrame()
        defense_df = pd.DataFrame()
        # read attack
        if info["attack"]:
            try:
                txt = info["attack"].read_text(encoding="utf-8", errors="ignore")
                attack_df = parse_attack_text(txt)
            except Exception as e:
                print(f"Error reading/parsing attack file {info['attack']}: {e}")
        # read defense
        if info["defense"]:
            try:
                txt = info["defense"].read_text(encoding="utf-8", errors="ignore")
                defense_df = parse_defense_text_strict(txt)
            except Exception as e:
                print(f"Error reading/parsing defense file {info['defense']}: {e}")

        per_war[key] = {"attack": attack_df, "defense": defense_df, "attack_path": info.get("attack_path"), "defense_path": info.get("defense_path")}

        # accumulate into season
        if not attack_df.empty:
            for t in ("Heroes","Titans"):
                sub = attack_df[attack_df["Type"]==t].groupby("Attacker")["Points"].sum()
                key_s = f"{t.lower()}_attack"
                for player, pts in sub.items():
                    season[key_s][player] = season[key_s].get(player, 0.0) + float(pts)
        if not defense_df.empty:
            for t in ("Heroes","Titans"):
                sub = defense_df[defense_df["Type"]==t]["Defender"].value_counts()
                key_s = f"{t.lower()}_defense"
                for player, cnt in sub.items():
                    season[key_s][player] = season[key_s].get(player, 0) + int(cnt)

    # Save season if requested
    if not args.no_save_season:
        save_season(season)
        print(f"Season saved to: {SEASON_FILE}")

    # Prepare Excel outputs: heroes.xlsx and titans.xlsx
    heroes_attack = []
    heroes_defense = []
    titans_attack = []
    titans_defense = []

    for date, data in per_war.items():
        a = data["attack"]
        d = data["defense"]
        if not a.empty:
            ha = a[a["Type"]=="Heroes"].groupby("Attacker")["Points"].sum().reset_index().sort_values("Points", ascending=False)
            ta = a[a["Type"]=="Titans"].groupby("Attacker")["Points"].sum().reset_index().sort_values("Points", ascending=False)
            ha["WarDate"] = date; ta["WarDate"] = date
            heroes_attack.append(ha); titans_attack.append(ta)
        if not d.empty:
            hd = d[d["Type"]=="Heroes"]["Defender"].value_counts().reset_index().rename(columns={"index":"Defender","Defender":"Count"})
            td = d[d["Type"]=="Titans"]["Defender"].value_counts().reset_index().rename(columns={"index":"Defender","Defender":"Count"})
            hd["WarDate"] = date; td["WarDate"] = date
            heroes_defense.append(hd); titans_defense.append(td)

    # concat per-war sheets (if empty, create empty df)
    heroes_attack_df = pd.concat(heroes_attack, ignore_index=True) if heroes_attack else pd.DataFrame(columns=["Attacker","Points","WarDate"])
    heroes_defense_df = pd.concat(heroes_defense, ignore_index=True) if heroes_defense else pd.DataFrame(columns=["Defender","Count","WarDate"])
    titans_attack_df = pd.concat(titans_attack, ignore_index=True) if titans_attack else pd.DataFrame(columns=["Attacker","Points","WarDate"])
    titans_defense_df = pd.concat(titans_defense, ignore_index=True) if titans_defense else pd.DataFrame(columns=["Defender","Count","WarDate"])

    # season summary dfs
    ha_season = pd.DataFrame(sorted(season.get("heroes_attack",{}).items(), key=lambda x:-x[1]), columns=["Attacker","Points"])
    ta_season = pd.DataFrame(sorted(season.get("titans_attack",{}).items(), key=lambda x:-x[1]), columns=["Attacker","Points"])
    hd_season = pd.DataFrame(sorted(season.get("heroes_defense",{}).items(), key=lambda x:-x[1]), columns=["Defender","Count"])
    td_season = pd.DataFrame(sorted(season.get("titans_defense",{}).items(), key=lambda x:-x[1]), columns=["Defender","Count"])

    # write heroes.xlsx and titans.xlsx
    out_heroes = Path("heroes.xlsx")
    out_titans = Path("titans.xlsx")
    with pd.ExcelWriter(out_heroes, engine="openpyxl") as writer:
        heroes_attack_df.to_excel(writer, sheet_name="Attack_Per_War", index=False)
        heroes_defense_df.to_excel(writer, sheet_name="Defense_Per_War", index=False)
        ha_season.to_excel(writer, sheet_name="Season_Attack", index=False)
        hd_season.to_excel(writer, sheet_name="Season_Defense", index=False)
    with pd.ExcelWriter(out_titans, engine="openpyxl") as writer:
        titans_attack_df.to_excel(writer, sheet_name="Attack_Per_War", index=False)
        titans_defense_df.to_excel(writer, sheet_name="Defense_Per_War", index=False)
        ta_season.to_excel(writer, sheet_name="Season_Attack", index=False)
        td_season.to_excel(writer, sheet_name="Season_Defense", index=False)

    print(f"Saved: {out_heroes.name}, {out_titans.name}")
    # also save a compact season_summary_all.xlsx
    out_compact = Path("season_summary_all.xlsx")
    with pd.ExcelWriter(out_compact, engine="openpyxl") as writer:
        ha_season.to_excel(writer, sheet_name="Heroes_Attack_Season", index=False)
        hd_season.to_excel(writer, sheet_name="Heroes_Defense_Season", index=False)
        ta_season.to_excel(writer, sheet_name="Titans_Attack_Season", index=False)
        td_season.to_excel(writer, sheet_name="Titans_Defense_Season", index=False)
    print(f"Saved: {out_compact.name}")

    # Print short console summary (season top 10)
    print("\n=== Season Top (Heroes Attack) ===")
    print(ha_season.head(10).to_string(index=False))
    print("\n=== Season Top (Titans Attack) ===")
    print(ta_season.head(10).to_string(index=False))
    print("\n=== Season Top (Heroes Defense) ===")
    print(hd_season.head(10).to_string(index=False))
    print("\n=== Season Top (Titans Defense) ===")
    print(td_season.head(10).to_string(index=False))

    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
