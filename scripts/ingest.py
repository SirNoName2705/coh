# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pyyaml",
#     "tiktoken",
#     "loguru",
#     "chromadb",
#     "fastembed",
#     "langchain-text-splitters"
# ]
# ///

import os
# Zwingt HuggingFace, echte Dateien statt Symlinks zu schreiben (verhindert ONNX-Crash)
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

import sys
import time
import signal
import shutil
from pathlib import Path
import yaml
import chromadb
from fastembed import TextEmbedding
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Einheitliches Logging aus dem Core-Modul
from src.core.logger import get_logger

logger = get_logger("ingest_pipeline")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "authors"
SHM_BASE = Path("/dev/shm/coh_ingest")


def cleanup_and_exit(sig=None, frame=None):
    logger.warning("Räume temporäre RAM-Disk auf...")
    if SHM_BASE.exists():
        shutil.rmtree(SHM_BASE, ignore_errors=True)
    if sig is not None:
        sys.exit(0)


signal.signal(signal.SIGINT, cleanup_and_exit)
signal.signal(signal.SIGTERM, cleanup_and_exit)


def clean_metadata_for_chroma(metadata: dict) -> dict:
    valid_meta = {}
    for k, v in metadata.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            valid_meta[k] = v
        elif isinstance(v, list):
            valid_meta[k] = ", ".join(map(str, v))
        else:
            valid_meta[k] = str(v)
    return valid_meta


def parse_markdown(file_path: Path):
    content = file_path.read_text(encoding="utf-8")
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            metadata = yaml.safe_load(parts[1]) or {}
            text = parts[2].strip()
            return metadata, text
    return {}, content.strip()


def run_ingest():
    if not DATA_DIR.exists():
        logger.error(f"Datenverzeichnis {DATA_DIR} fehlt!")
        return

    author_dirs = [d for d in DATA_DIR.iterdir() if d.is_dir()]
    if not author_dirs:
        logger.warning(f"Keine Autoren-Ordner in {DATA_DIR} gefunden.")
        return

    SHM_BASE.mkdir(parents=True, exist_ok=True)

    logger.info("Initialisiere FastEmbed TextEmbedding (jina-embeddings-v3) mit CUDA...")
    embedding_model = TextEmbedding(
        model_name="jinaai/jina-embeddings-v3",
        cache_dir="/mnt/MassStorage/.cache/AI/fastembed",
        threads=8,  # Reduziert, schont den RAM und reicht völlig aus, da die GPU die Hauptlast trägt
        providers=["CUDAExecutionProvider"]
    )

    text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=500,
        chunk_overlap=100
    )

    for author_dir in author_dirs:
        author_slug = author_dir.name
        start_time = time.perf_counter()
        logger.info(f"Starte Ingestion für: {author_slug}")

        shm_author_dir = SHM_BASE / author_slug
        if shm_author_dir.exists():
            shutil.rmtree(shm_author_dir)
        shm_author_dir.mkdir(parents=True, exist_ok=True)
        final_db_dir = author_dir / "chroma_db"

        batch_texts, batch_metadatas, batch_ids = [], [], []

        book_dirs = [b for b in author_dir.iterdir() if b.is_dir() and b.name != "chroma_db"]
        for book_dir in book_dirs:
            asin = book_dir.name.split("_")[-1] if "_" in book_dir.name else "unknown"
            md_files = sorted(list(book_dir.rglob("content/*.md")))

            for md_file in md_files:
                metadata, text = parse_markdown(md_file)
                if not text:
                    continue

                chunks = text_splitter.split_text(text)
                book_title = metadata.get("book", book_dir.name)
                chapter_nr = metadata.get("chapter_nr", md_file.stem.split("_")[-1])
                chapter_title = metadata.get("title", "Ohne Titel")

                for idx, raw_chunk in enumerate(chunks):
                    chunk_id = f"{author_slug}_{asin}_{md_file.stem}_chunk{idx}"
                    header = f"[Quelle: {book_title} | Kapitel: {chapter_nr} - {chapter_title}]\n\n"

                    batch_texts.append(header + raw_chunk)
                    batch_ids.append(chunk_id)
                    batch_metadatas.append(clean_metadata_for_chroma({
                        **metadata,
                        "author_slug": author_slug,
                        "asin": asin,
                        "source_file": md_file.name,
                        "chunk_idx": idx,
                        "total_chunks": len(chunks)
                    }))

        if not batch_texts:
            logger.info(f"Keine Markdown-Inhalte für {author_slug} gefunden. Überspringe...")
            continue

        logger.info(f"Berechne Embeddings für {len(batch_texts)} Chunks...")
        batch_embeddings = list(embedding_model.embed(batch_texts, batch_size=32))

        logger.info(f"Indexiere in RAM-ChromaDB (/dev/shm)...")
        client = chromadb.PersistentClient(path=str(shm_author_dir))
        collection = client.get_or_create_collection(name="langchain")

        chunk_batch_size = 500
        for i in range(0, len(batch_texts), chunk_batch_size):
            collection.add(
                ids=batch_ids[i:i + chunk_batch_size],
                embeddings=[e.tolist() for e in batch_embeddings[i:i + chunk_batch_size]],
                metadatas=batch_metadatas[i:i + chunk_batch_size],
                documents=batch_texts[i:i + chunk_batch_size]
            )

        logger.info(f"Verschiebe Index auf Ziellaufwerk: {final_db_dir}")
        if final_db_dir.exists():
            shutil.rmtree(final_db_dir)
        shutil.copytree(shm_author_dir, final_db_dir)
        shutil.rmtree(shm_author_dir)

        duration = time.perf_counter() - start_time
        logger.info(f"Autor {author_slug} abgeschlossen ({duration:.2f}s).")

    cleanup_and_exit()
    logger.info("Ingestion-Pipeline vollständig beendet.")


if __name__ == "__main__":
    run_ingest()