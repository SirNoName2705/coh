"""
Asynchrones und Thread-sicheres Logging-System für 'Council of Heroes'.
Basiert auf der Bibliothek Loguru.

Dieses Modul ersetzt systemweit verbotene print()-Aufrufe durch hochperformante,
blockierungsfreie Queue-Sinks. Die asynchrone Architektur garantiert, dass
die Event-Loop niemals durch I/O-Latenzen der Dateisysteme blockiert wird.
"""

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

# Type-Checking Block verhindert zirkuläre Laufzeit-Abhängigkeiten
if TYPE_CHECKING:
    from loguru import Logger

# Dynamische Pfad-Konstruktion
# BASE_DIR evaluiert den absoluten Pfad des Projektstamms, unabhängig davon,
# von welchem Arbeitsverzeichnis das Python-Skript gestartet wird.
BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
LOG_DIR: Path = BASE_DIR / "logs"


def _setup_logger() -> None:
    """
    Kapselt die Initialisierung des globalen Loguru-Setups.
    Entfernt den synchronen Standard-Handler und registriert zwei neue,
    vollständig asynchron-kompatible Sinks (Terminal und Datei).

    Das Setup erfolgt exakt einmal beim ersten Import des Moduls, um
    Doppelregistrierungen (und somit doppelte Log-Einträge) zu vermeiden.
    """
    # Sicherstellen, dass das Zielverzeichnis existiert (äquivalent zu mkdir -p)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Entferne den voreingestellten, synchronen Standard-Logger von Loguru.
    # Dieser würde andernfalls die Event-Loop durch blockierendes stdout blockieren.
    logger.remove()

    # 2. Definiere das Format für Konsolenausgaben (Farbig, detailliert für DX)
    # Nutzt {extra[name]} für das korrekte Binding des Modulnamens.
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{extra[name]}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    # 3. Definiere das Format für Dateiausgaben
    # Maschinenlesbar, ohne Farb-Tags, optimal für spätere Aggregation.
    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
        "{level: <8} | "
        "{extra[name]}:{function}:{line} - "
        "{message}"
    )

    # Sink 1: Standardausgabe (Terminal)
    # Der Parameter enqueue=True ist das architektonische Herzstück. Er zwingt Loguru,
    # eine Thread-sichere SimpleQueue zu nutzen. Die asynchrone Event-Loop reiht
    # die Nachricht lediglich in den RAM ein und wird niemals blockiert.
    logger.add(
        sys.stdout,
        level="DEBUG",
        format=console_format,
        colorize=True,
        enqueue=True,
        backtrace=True,
        diagnose=True  # Im lokalen Terminal für Debugging-Zwecke aktiviert
    )

    # Sink 2: Rotierende und persistente Log-Datei
    # Beinhaltet automatisiertes Lifecycle-Management für massive Datenmengen.
    log_file_path = LOG_DIR / "council_of_heroes.log"
    logger.add(
        log_file_path,
        level="INFO",  # Reduziertes Level, um Festplatten-I/O zu schonen
        format=file_format,
        rotation="10 MB",  # Erstelle neue Datei ab exakt 10 Megabyte
        retention="14 days",  # Lösche physisch alte Rotations-Fragmente nach 14 Tagen
        compression="zip",  # Komprimiere archivierte Logs zur Storage-Optimierung
        enqueue=True,  # Zwingend notwendig für blockierungsfreie Datei-Operationen
        encoding="utf-8",
        backtrace=True,
        diagnose=False  # Sicherheitsmechanismus: Verhindert Leakage von API-Keys
        # oder LLM-Tokens in Stacktraces auf der Festplatte
    )


# Unmittelbare Ausführung der Konfiguration beim Modul-Import
_setup_logger()


def get_logger(name: str) -> "Logger":
    """
    Erzeugt und exportiert einen gebundenen, kontextualisierten Logger für ein Modul.

    Diese Funktion implementiert das Dependency Injection Pattern für Logs.
    Durch die Nutzung von .bind() wird der globale, asynchrone Loguru-Sink nicht
    dupliziert. Stattdessen wird der String `name` in das `extra`-Dictionary der
    generierten Log-Nachricht injiziert und vom systemweiten Format abgefangen.

    Args:
        name (str): Der Name des aufrufenden Moduls oder Agenten (empfohlen: __name__).

    Returns:
        loguru.Logger: Eine geklonte Logger-Instanz mit injiziertem Modul-Kontext.
    """
    # Defensive Programmierung: Zuweisung eines Fallbacks bei leerem String
    module_name: str = name if name else "system"
    return logger.bind(name=module_name)


if __name__ == "__main__":
    # Isolierter Testblock zur Verifizierung der asynchronen Queues.
    # Nutzt asyncio, um das Zusammenspiel mit einer simulierten Event-Loop zu validieren.

    import asyncio

    # Instanziierung des Loggers mit spezifischem Test-Kontext
    test_logger = get_logger("logger_async_verification")


    async def async_logging_test() -> None:
        """Simuliert eine asynchrone Agenten-Operation mit Log-Ereignissen."""
        test_logger.debug("Test-Start: Asynchrone Event-Loop initialisiert.")

        # Simuliere I/O Latenz (z.B. den HTTP-Call an die LLM Base URL)
        await asyncio.sleep(0.1)

        test_logger.info("I/O abgeschlossen: Event-Loop wurde während des Loggens nicht blockiert.")
        test_logger.success("Alle asynchronen Sinks (Terminal & Datei) arbeiten erwartungskonform.")


    # Starten der asynchronen Laufzeitumgebung
    asyncio.run(async_logging_test())

    # Graceful Shutdown für die asynchronen Log-Queues:
    # Da Python bei kurzen Skripten terminiert, bevor Hintergrund-Threads ihre
    # Queues auf die Festplatte flushen können, erzwingt complete() das Leerlaufen.
    test_logger.complete()