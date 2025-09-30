import sys
import pandas as pd
import os

def parse_attack_text(text):
    rows = []
    for line in text.splitlines():
        cols = [c.strip() for c in line.split(",")]
        if len(cols) >= 5:
            attacker = cols[2]
            result = cols[1].lower()
            try:
                points = int(cols[3].replace("+", "").replace("-", ""))
            except:
                points = 0
            tipo = "Heroes" if "Hero" in cols[0] else "Titans"
            rows.append({"Player": attacker, "Result": result, "Points": points, "Type": tipo})
    return pd.DataFrame(rows)

def parse_defense_text(text):
    rows = []
    for line in text.splitlines():
        cols = [c.strip() for c in line.split(",")]
        if len(cols) >= 3:
            defender = cols[2]  # il difensore è nella terza colonna
            result = cols[1].lower()
            if "defeat" in result:  # se l’attaccante perde → difesa riuscita
                tipo = "Heroes" if "Hero" in cols[0] else "Titans"
                rows.append({"Player": defender, "Result": "Defense Success", "Points": 1, "Type": tipo})
    return pd.DataFrame(rows)

def read_log_file(filename):
    with open(filename, encoding="utf-8", errors="ignore") as f:
        text = f.read()
    if "Attack Log" in filename:
        df = parse_attack_text(text)
        df["Source"] = "attack"
    elif "Defense Log" in filename:
        df = parse_defense_text(text)
        df["Source"] = "defense"
    else:
        df = pd.DataFrame()
    return df

def main():
    if len(sys.argv) < 2:
        print("Usage: python cow_analyzer.py <log files>")
        sys.exit(1)

    per_war = {}
    for fn in sys.argv[1:]:
        war = os.path.basename(fn).split(" Server")[0]
        df = read_log_file(fn)
        if war not in per_war:
            per_war[war] = {"attack": pd.DataFrame(), "defense": pd.DataFrame()}
        if "attack" in fn.lower():
            per_war[war]["attack"] = pd.concat([per_war[war]["attack"], df])
        elif "defense" in fn.lower():
            per_war[war]["defense"] = pd.concat([per_war[war]["defense"], df])

    for war, dfs in per_war.items():
        total_attack = dfs["attack"]["Points"].sum() if not dfs["attack"].empty else 0
        total_defense = dfs["defense"]["Points"].sum() if not dfs["defense"].empty else 0
        print(f"Totale gilda {war}: {total_attack + total_defense}")

    # export dettagli giocatori
    ha_season = pd.concat([df[df["Type"]=="Heroes"] for d in per_war.values() if not d["attack"].empty for df in [d["attack"]]])
    ta_season = pd.concat([df[df["Type"]=="Titans"] for d in per_war.values() if not d["attack"].empty for df in [d["attack"]]])
    hd_season = pd.concat([df[df["Type"]=="Heroes"] for d in per_war.values() if not d["defense"].empty for df in [d["defense"]]])
    td_season = pd.concat([df[df["Type"]=="Titans"] for d in per_war.values() if not d["defense"].empty for df in [d["defense"]]])

    with pd.ExcelWriter("heroes.xlsx") as writer:
        if not ha_season.empty:
            ha_season.groupby("Player").sum(numeric_only=True).to_excel(writer, sheet_name="Heroes Attack")
        if not hd_season.empty:
            hd_season.groupby("Player").sum(numeric_only=True).to_excel(writer, sheet_name="Heroes Defense")
    with pd.ExcelWriter("titans.xlsx") as writer:
        if not ta_season.empty:
            ta_season.groupby("Player").sum(numeric_only=True).to_excel(writer, sheet_name="Titans Attack")
        if not td_season.empty:
            td_season.groupby("Player").sum(numeric_only=True).to_excel(writer, sheet_name="Titans Defense")

if __name__ == "__main__":
    main()
