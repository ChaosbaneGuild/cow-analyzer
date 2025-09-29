# patch_replace.py
# Eseguire nella stessa cartella di cow_dashboard_full.py
from pathlib import Path
import re, textwrap, sys

p = Path("cow_dashboard_full.py")
if not p.exists():
    print("ERRORE: file 'cow_dashboard_full.py' non trovato nella cartella corrente:", Path('.').resolve())
    sys.exit(1)

s = p.read_text(encoding="utf-8")

# Normalizziamo i tab in spazi per evitare mismatch di indentazione
s = s.replace("\t", "    ")

# Troviamo la riga che contiene st.write("File salvati:", processed)
m = re.search(r'^[ \t]*st\.write\("File salvati:", processed\).*$' , s, flags=re.MULTILINE)
if not m:
    print("Non ho trovato la riga 'st.write(\"File salvati:\", processed)'. Controlla manualmente il file.")
    sys.exit(1)

old_line = m.group(0)
# Prendiamo l'indentazione della riga trovata
indent = re.match(r'^([ \t]*)', old_line).group(1)

# Blocco di sostituzione (non triplichiamo virgolette, useremo textwrap.indent)
block = """st.write("File salvati:", processed)
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
"""

replacement = textwrap.indent(block, indent)

# Sostituisci SOLO la prima occorrenza della riga trovata (non tocchiamo altro)
new_s = s.replace(old_line, replacement, 1)

# Salva backup e file modificato
bak = p.with_suffix(".py.bak")
bak.write_text(s, encoding="utf-8")
p.write_text(new_s, encoding="utf-8")

print("Patch applicata con successo. Backup salvato come:", bak.name)
