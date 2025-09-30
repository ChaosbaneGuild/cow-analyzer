import sys
import argparse
from pathlib import Path
import re
import json
import pandas as pd

# ----------------- helper functions -----------------
def parse_attack_text(text):
    rows = []
    for line in text.splitlines():
        cols = [c.strip() for c in line.split(",")]
        if len(cols) >= 4 and cols[1] in ("Victory", "Defeat"):
            try:
                pts = float(cols[2].replace("+", ""))
            except:
                pts = 0
            rows.append({"Player": cols[0], "Result": cols[1], "Points": pts, "Type": cols[3]})
        elif len(cols) >= 3 and cols[1] == "Fortification captured":
            try:
                pts = float(cols[2].replace("+", ""))
            except:
                pts = 0
            rows.append({"Player": cols[0], "Result": "Fortification captured", "Points": pts, "Type": "Bonus"})
    return pd.DataFrame(rows)

def parse_defense_text_strict(text):
    rows = []
    for line in text.splitlines():
        cols = [c.strip() for c in line.split(",")]
        if len(cols) >= 3 and cols[1] == "Defense Victory":
            rows.append({"Player": cols[0], "Result": "Defense Victory", "Points": 1, "Type": cols[2]})
    return pd.DataFrame(rows)

def load_season():
    season_file = Path("season_scores.json")
    if season_file.exists():
        return json.loads(season_file.read_text(encoding="utf-8"))
    return {}

def save_season(season):
    season_file = Path("season_scores.json")
    season_file.write_text(json.dumps(season, indent=2), encoding="utf-8")

# ----------------- calcolo punteggio totale gilda -----------------
def compute_guild_score(text):
    total = 0.0
    for line in text.splitlines():
        cols = [c.strip() for c in line.split(",")]
        if len(cols) >= 4 and cols[1] in ("Victory", "Defeat") and cols[2].startswith("+"):
            try:
                total += float(cols[2].replace("+", ""))
            except:
                continue
        elif len(cols) >= 3 and cols[1] == "Fortification captured" and cols[2].startswith("+"):
            try:
                total += float(cols[2].replace("+", ""))
            except:
                continue
    return total

# ----------------- nuova funzione export HTML -----------------
def export_html(ha_season, hd_season, ta_season, td_season, guild_scores):
    html_template = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>CoW Guild Rankings</title>
        <!-- Bootstrap -->
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        <!-- DataTables -->
        <link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/dataTables.bootstrap5.min.css">
    </head>
    <body class="bg-light">
        <div class="container py-4">
            <h1 class="text-center mb-4">🏆 CoW Guild Rankings</h1>

            <h2>Guild Scores per War</h2>
            {guild_scores.to_html(index=False, classes="table table-striped table-bordered", border=0)}

            <h2>Heroes Attack (Season)</h2>
            {ha_season.to_html(index=False, classes="table table-striped table-bordered", border=0)}

            <h2>Heroes Defense (Season)</h2>
            {hd_season.to_html(index=False, classes="table table-striped table-bordered", border=0)}

            <h2>Titans Attack (Season)</h2>
            {ta_season.to_html(index=False, classes="table table-striped table-bordered", border=0)}

            <h2>Titans Defense (Season)</h2>
            {td_season.to_html(index=False, classes="table table-striped table-bordered", border=0)}
        </div>

        <!-- JS -->
        <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
        <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
        <script src="https://cdn.datatables.net/1.13.6/js/dataTables.bootstrap5.min.js"></script>
        <script>
            $(document).ready(function(){{
                $('table').DataTable();
            }});
        </script>
    </body>
    </html>
    """

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_template)
    print("✅ Generato index.html con tabelle migliorate per GitHub Pages")

# ----------------- main -----------------
def main(argv):
    parser = argparse.ArgumentParser(description="Process CoW logs and generate ranking files")
    parser.add_argument("files", nargs="*", help="CSV log files (globs allowed). If none, all *.csv in cwd are processed.")
    parser.add_argument("--no-save-season", action="store_true", help="Do not update season_scores.json")
    args = parser.parse_args(argv)

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

    groups = {}
    for p in files:
        m = re.match(r"(\d{2}-\d{2}-\d{4})", p.name)
        key = m.group(1) if m else p.name
        groups.setdefault(key, {"attack": None, "defense": None})
        if "attack log" in p.name.lower():
            groups[key]["attack"] = p
        if "defense log" in p.name.lower():
            groups[key]["defense"] = p

    season = load_season()
    per_war = {}

    for key, info in sorted(groups.items(), key=lambda x: x[0]):
        attack_df = pd.DataFrame()
        defense_df = pd.DataFrame()
        guild_score = None

        if info["attack"]:
            try:
                txt = info["attack"].read_text(encoding="utf-8", errors="ignore")
                attack_df = parse_attack_text(txt)
                guild_score = compute_guild_score(txt)
            except Exception as e:
                print(f"Error parsing attack file {info['attack']}: {e}")

        if info["defense"]:
            try:
                txt = info["defense"].read_text(encoding="utf-8", errors="ignore")
                defense_df = parse_defense_text_strict(txt)
            except Exception as e:
                print(f"Error parsing defense file {info['defense']}: {e}")

        per_war[key] = {"attack": attack_df, "defense": defense_df, "guild_score": guild_score}
        if guild_score is not None:
            print(f"Totale gilda {key}: {guild_score}")

    ha_season = pd.concat([df[df["Type"]=="Heroes"] for d in per_war.values() if not d["attack"].empty for df in [d["attack"]]])
    hd_season = pd.concat([df[df["Type"]=="Heroes"] for d in per_war.values() if not d["defense"].empty for df in [d["defense"]]])
    ta_season = pd.concat([df[df["Type"]=="Titans"] for d in per_war.values() if not d["attack"].empty for df in [d["attack"]]])
    td_season = pd.concat([df[df["Type"]=="Titans"] for d in per_war.values() if not d["defense"].empty for df in [d["defense"]]])

    ha_season = ha_season.groupby("Player", as_index=False)["Points"].sum().sort_values("Points", ascending=False)
    hd_season = hd_season.groupby("Player", as_index=False)["Points"].sum().sort_values("Points", ascending=False)
    ta_season = ta_season.groupby("Player", as_index=False)["Points"].sum().sort_values("Points", ascending=False)
    td_season = td_season.groupby("Player", as_index=False)["Points"].sum().sort_values("Points", ascending=False)

    guild_scores = pd.DataFrame(
        [(date, data.get("guild_score", None)) for date, data in per_war.items()],
        columns=["WarDate", "GuildScore"]
    )

    out_compact = Path("season_summary_all.xlsx")
    with pd.ExcelWriter(out_compact, engine="openpyxl") as writer:
        ha_season.to_excel(writer, sheet_name="Heroes_Attack_Season", index=False)
        hd_season.to_excel(writer, sheet_name="Heroes_Defense_Season", index=False)
        ta_season.to_excel(writer, sheet_name="Titans_Attack_Season", index=False)
        td_season.to_excel(writer, sheet_name="Titans_Defense_Season", index=False)
        guild_scores.to_excel(writer, sheet_name="Guild_Scores", index=False)

    print(f"Saved: {out_compact.name}")

    export_html(ha_season, hd_season, ta_season, td_season, guild_scores)

    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))