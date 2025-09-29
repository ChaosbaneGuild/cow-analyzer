# replace_rerun_all.py
# Esegui questo script nella stessa cartella di cow_dashboard_full.py
# Sostituisce tutte le occorrenze di st.experimental_rerun() con un blocco compatibile
from pathlib import Path
import re
p = Path("cow_dashboard_full.py")
if not p.exists():
    print("File cow_dashboard_full.py non trovato nella cartella corrente:", p.resolve())
    raise SystemExit(1)

txt = p.read_text(encoding="utf-8")

pattern = re.compile(r'(?m)^(?P<indent>[ \t]*)st\.experimental_rerun\(\)\s*$')

def repl(m):
    indent = m.group("indent")
    block = (
        "try:\n"
        "    if hasattr(st, \"experimental_rerun\"):\n"
        "        st.experimental_rerun()\n"
        "    else:\n"
        "        raise AttributeError\n"
        "except Exception:\n"
        "    st.info(\n"
        "        \"I file sono stati salvati nella cartella logs/. \"\n"
        "        \"Ricarica manualmente la pagina (F5) per visualizzare i file salvati, \"\n"
        "        \"oppure vai su 'Scansiona cartella logs' e premi 'Processa selezionati'.\"\n"
        "    )"
    )
    # indent each line of block with same indent as original
    return indent + block.replace("\n", "\n" + indent)

new_txt, n = pattern.subn(repl, txt)

if n == 0:
    print("Nessuna occorrenza di st.experimental_rerun() trovata.")
else:
    bak = p.with_suffix(".rerunpatched.py.bak")
    bak.write_text(txt, encoding="utf-8")
    p.write_text(new_txt, encoding="utf-8")
    print(f"Sostituite {n} occorrenze. Backup salvato come: {bak.name}")
