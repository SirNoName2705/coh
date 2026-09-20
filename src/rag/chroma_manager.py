import asyncio
import logging
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from langchain_chroma import Chroma
from src.config import get_settings

# Nativer Import statt LangChain-Community
from fastembed import TextEmbedding

logger = logging.getLogger(__name__)


# --- ADAPTER: Macht natives FastEmbed kompatibel mit LangChain ---
class NativeFastEmbedAdapter:
    def __init__(self, **kwargs):
        # Initialisiert die C++ ONNX Engine
        self.model = TextEmbedding(**kwargs)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [e.tolist() for e in self.model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        # Generiert Vektor für die Frage des Agenten
        return list(self.model.embed([text]))[0].tolist()


# Globale Variablen im isolierten Worker-RAM
_WORKER_EMBEDDINGS = None
_WORKER_CHROMA_CACHE = {}


def _init_worker():
    """Wird 1x pro CPU-Kern beim Start des Workers ausgeführt."""
    global _WORKER_EMBEDDINGS

    # Richtiges lokales Worker-Logging!
    from src.core.logger import get_logger
    worker_logger = get_logger("rag_worker")
    worker_logger.info("Initialisiere CPU-Worker für RAG...")

    # 4 Threads pro Worker auf der CPU, CUDA-Warnungen unterdrückt
    _WORKER_EMBEDDINGS = NativeFastEmbedAdapter(
        model_name="jinaai/jina-embeddings-v3",
        cache_dir="/mnt/MassStorage/.cache/AI/fastembed",
        threads=4,
        providers=["CPUExecutionProvider"]
    )


def _worker_query(author_slug: str, query: str, k: int = 3) -> str:
    """Synchroner RAG-Abruf innerhalb des dedizierten Worker-Prozesses."""
    global _WORKER_EMBEDDINGS, _WORKER_CHROMA_CACHE

    settings = get_settings()
    db_path = Path(settings.data_dir) / "authors" / author_slug / "chroma_db"

    if not db_path.exists():
        return "Kein spezifisches Wissen zu diesem Autor gefunden."

    if author_slug not in _WORKER_CHROMA_CACHE:
        _WORKER_CHROMA_CACHE[author_slug] = Chroma(
            persist_directory=str(db_path),
            embedding_function=_WORKER_EMBEDDINGS
        ).as_retriever(search_kwargs={"k": k})

    retriever = _WORKER_CHROMA_CACHE[author_slug]
    docs = retriever.invoke(query)
    return "\n\n".join([doc.page_content for doc in docs])


class RagManager:
    def __init__(self):
        self.settings = get_settings()
        self.executor = None

    def start(self):
        logger.info(f"Starte ProcessPoolExecutor mit {self.settings.max_workers} RAG-Workern...")
        self.executor = ProcessPoolExecutor(
            max_workers=self.settings.max_workers,
            initializer=_init_worker
        )

    def stop(self):
        if self.executor:
            logger.info("Fahre RAG-Worker herunter...")
            self.executor.shutdown(wait=True)

    async def query_context(self, author_slug: str, query: str, k: int = 3) -> str:
        if not self.executor:
            logger.warning("RagManager Executor nicht gestartet!")
            return ""

        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(
                self.executor,
                _worker_query,
                author_slug,
                query,
                k
            )
        except Exception as e:
            logger.error(f"RAG-Fehler für {author_slug}: {e}", exc_info=True)
            return ""


# Singleton für den App-Lifecycle
rag_manager = RagManager()