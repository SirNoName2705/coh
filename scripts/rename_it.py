import logging
import re
from pathlib import Path

# --- Konfiguration für PyCharm Run ---
BASE_DIR = Path("../data/authors")
DRY_RUN = False  # Auf True setzen, wenn du erst testen willst
LOG_LEVEL = logging.INFO

CHAPTER_REGEX = re.compile(r"^chapter_(\d+)\.md$", re.IGNORECASE)


def setup_logging() -> None:
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def process_content_dir(content_dir: Path, dry_run: bool) -> int:
    matches: list[tuple[Path, int]] = []

    for file_path in content_dir.iterdir():
        if file_path.is_file():
            match = CHAPTER_REGEX.match(file_path.name)
            if match:
                matches.append((file_path, int(match.group(1))))

    if not matches:
        return 0

    # Ermittelt Stellen für Padding (mindestens 3: 001, 002, ...)
    max_chapter = max(num for _, num in matches)
    pad_width = max(3, len(str(max_chapter)))

    renamed_count = 0

    for old_path, num in sorted(matches, key=lambda x: x[1]):
        new_name = f"chapter_{num:0{pad_width}d}.md"
        new_path = old_path.with_name(new_name)

        if old_path == new_path:
            continue

        if new_path.exists():
            logging.warning("Kollision! Ziel existiert schon: %s", new_name)
            continue

        if dry_run:
            logging.info("[DRY-RUN] %s -> %s", old_path.name, new_name)
        else:
            logging.info("Renaming: %s -> %s", old_path.name, new_name)
            old_path.rename(new_path)

        renamed_count += 1

    return renamed_count


def main() -> None:
    setup_logging()

    if not BASE_DIR.exists():
        logging.error("Basispfad nicht gefunden: %s", BASE_DIR.resolve())
        return

    content_dirs = [p for p in BASE_DIR.rglob("content") if p.is_dir()]
    if not content_dirs:
        logging.warning("Keine 'content'-Ordner unter %s gefunden.", BASE_DIR)
        return

    logging.info(
        "Starte %s in %s (%d Bücher gefunden)...",
        "DRY-RUN" if DRY_RUN else "RENAME",
        BASE_DIR,
        len(content_dirs),
    )

    total_renamed = 0
    for c_dir in content_dirs:
        total_renamed += process_content_dir(c_dir, dry_run=DRY_RUN)

    logging.info(
        "Fertig. Insgesamt %d Dateien %s.",
        total_renamed,
        "simuliert" if DRY_RUN else "umbenannt",
    )


if __name__ == "__main__":
    main()