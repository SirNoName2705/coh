# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = [
#     "chromadb>=0.4.0",
#     "numpy<2.0.0",
#     "pandas>=2.1.0,<2.3.0",
#     "pydantic>=2.5.0,<2.8.0",
#     "fastapi>=0.104.0,<0.110.0",
#     "renumics-spotlight[analyzers]==1.8.2",
# ]
# ///
import logging
import sys
from pathlib import Path
import chromadb
import numpy as np
import pandas as pd
from renumics import spotlight

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUTHORS_DIR = PROJECT_ROOT / "data" / "authors"
logger = logging.getLogger(__name__)




def load_author_collection(author_name: str, method_label: str) -> list[dict]:
    db_path = AUTHORS_DIR / author_name / "chroma_db"
    if not db_path.exists():
        logger.error(f"Pfad existiert nicht: {db_path}")
        return []

    logger.info(f"Lade '{author_name}' ({method_label}) aus {db_path}...")
    client = chromadb.PersistentClient(path=str(db_path))

    collections = client.list_collections()
    if not collections:
        logger.warning(f"Keine Collections in {author_name} gefunden.")
        return []

    col_name = "langchain" if any(c.name == "langchain" for c in collections) else collections[0].name
    collection = client.get_collection(name=col_name)

    data = collection.get(include=["documents", "embeddings", "metadatas"])
    records = []

    for cid, doc, emb, meta in zip(
        data["ids"],
        data["documents"],
        data["embeddings"],
        data["metadatas"] or [{}] * len(data["ids"]),
    ):
        if isinstance(emb, dict):
            logger.error(f"🚨 ALARM: Embedding für {cid} ist ein Dict!")
            continue

        meta_clean = meta if isinstance(meta, dict) else {}

        records.append({
            "id": str(cid),
            "document": str(doc),
            "method": method_label,
            "author": author_name,
            "book": meta_clean.get("book", "unknown"),
            "chapter_nr": str(meta_clean.get("chapter_nr", "")),
            "chunk_idx": meta_clean.get("chunk_idx", -1),
            "embedding": np.array(emb, dtype=np.float32),
        })

    logger.info(f"    -> {len(records)} Chunks geladen.")
    return records


# def main():
#     #dale_carnegie_late_aggregate ist neustes, aber wir wollen alle 3 vergleichen
#     if len(sys.argv) >= 3:
#         target_default = sys.argv[1]
#         target_late = sys.argv[2]
#     elif len(sys.argv) == 2:
#         target_default = sys.argv[1]
#         target_late = f"{sys.argv[1]}_late"
#     else:
#         target_default = "dale_carnegie"
#         target_late = "dale_carnegie_late"
#
#     records = []
#     records.extend(load_author_collection(target_default, method_label="standard"))
#     records.extend(load_author_collection(target_late, method_label="late_chunking"))
#
#     if not records:
#         logger.warning("[!] Keine Daten zum Visualisieren gefunden. Beende.")
#         return
#
#     df = pd.DataFrame(records)
#     logger.info(f"[*] DataFrame vorbereitet: {len(df)} Zeilen. Starte Spotlight...")
#
#     spotlight.show(
#         df,
#         dtype={
#             "embedding": spotlight.Embedding,
#             "method": spotlight.Category,
#             "author": spotlight.Category,
#             "book": spotlight.Category,
#         },
#         port=5000,
#         wait=True,
#     )

def derive_method_label(collection_name: str) -> str:
    """Bestimmt anhand von Namenskonventionen das Spotlight-Kategorielabel."""
    if collection_name.endswith("_late_aggregate"):
        return "late_aggregate"
    if collection_name.endswith("_late"):
        return "late_chunking"
    return "standard"


def main():
    default_base = "dale_carnegie"
    variants = ["", "_late", "_late_aggregate"]

    # 1. Targets dynamisch auflösen
    if len(sys.argv) > 2:
        # Beliebig viele explizite Collections via CLI: python script.py c1 c2 c3 c4 ...
        targets = sys.argv[1:]
    elif len(sys.argv) == 2:
        # Genau 1 Basis-Präfix übergeben -> generiert das 3er-Set für diesen Autor
        base = sys.argv[1]
        targets = [f"{base}{suffix}" for suffix in variants]
    else:
        # Fallback: Dale Carnegie Komplettvergleich
        targets = [f"{default_base}{suffix}" for suffix in variants]

    # 2. Beliebig viele Collections per Loop laden
    records = []
    for target in targets:
        method = derive_method_label(target)
        logger.info(f"Lade Collection '{target}' (Method: '{method}')...")
        try:
            batch = load_author_collection(target, method_label=method)
            if batch:
                records.extend(batch)
            else:
                logger.warning(f"Keine Einträge für '{target}' gefunden.")
        except Exception as e:
            logger.error(f"Fehler beim Laden von '{target}': {e}")

    if not records:
        logger.warning("Keine Daten zum Visualisieren gefunden. Beende.")
        return

    # 3. DataFrame aufbereiten & visualisieren
    df = pd.DataFrame(records)
    logger.info(
        f"DataFrame vorbereitet: {len(df)} Zeilen aus {len(targets)} Collections. Starte Spotlight..."
    )

    spotlight.show(
        df,
        dtype={
            "embedding": spotlight.Embedding,
            "method": spotlight.Category,
            "author": spotlight.Category,
            "book": spotlight.Category,
        },
        port=5000,
        wait=True,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    main()