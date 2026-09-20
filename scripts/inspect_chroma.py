"""
Interaktive UMAP-Visualisierung der ChromaDB für einen Autor.
Starten mit: uv run scripts/inspect_chroma.py dale_carnegie
"""
import sys
from pathlib import Path
import chromadb
import pandas as pd
from renumics import spotlight

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUTHORS_DIR = PROJECT_ROOT / "data" / "authors"

def main():
    # Autor über Argument oder Standardwert
    author_slug = sys.argv[1] if len(sys.argv) > 1 else "dale_carnegie"
    db_path = AUTHORS_DIR / author_slug / "chroma_db"

    if not db_path.exists():
        print(f"[ERROR] Pfad existiert nicht: {db_path}")
        return

    print(f"[*] Lade ChromaDB für '{author_slug}' aus {db_path}...")
    # Read-Only Zugriff auf die SQLite (umgeht File-Locks während deine RAG-Worker laufen)
    client = chromadb.PersistentClient(path=str(db_path))

    collections = client.list_collections()
    if not collections:
        print("[ERROR] Keine Collections in dieser ChromaDB gefunden!")
        return

    col_name = "langchain" if any(c.name == "langchain" for c in collections) else collections[0].name
    collection = client.get_collection(name=col_name)

    print(f"[*] Extrahiere Embeddings und Metadaten aus '{col_name}'...")
    # Wir holen ALLES, um den Vektorraum abzubilden
    data = collection.get(include=["documents", "metadatas", "embeddings"])

    if not data["ids"]:
        print("[!] Collection ist leer.")
        return

    print(f"[*] {len(data['ids'])} Chunks geladen. Bereite DataFrame vor...")
    records = []
    for cid, doc, meta, emb in zip(data["ids"], data["documents"], data["metadatas"], data["embeddings"]):
        entry = {
            "id": cid,
            "document": doc,
            "char_count": len(doc),
            "embedding": emb,
        }
        if meta:
            entry.update(meta)  # YAML-Frontmatter (chapter_nr, title etc.) als separate Spalten anlegen
        records.append(entry)

    df = pd.DataFrame(records)

    print("[*] Starte Spotlight UI im Browser... (Beenden mit Strg+C)")
    # Spotlight erkennt die 'embedding'-Spalte und berechnet automatisch die UMAP-Projektion
    spotlight.show(
        df,
        dtype={"embedding": spotlight.Embedding},
        port=5000,
        wait=True
    )

if __name__ == "__main__":
    main()