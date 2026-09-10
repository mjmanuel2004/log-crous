"""Gère la persistance des IDs d'annonces déjà notifiées, pour ne signaler
que les *nouvelles* annonces à chaque exécution.

Le fichier JSON est commité dans le repo par le workflow GitHub Actions
après chaque run (voir .github/workflows/crous-watch.yml), ce qui lui
permet de "survivre" d'une exécution à l'autre malgré le fait que chaque
run GitHub Actions démarre sur une machine neuve.
"""

import json
import logging
from pathlib import Path
from typing import Set

logger = logging.getLogger(__name__)


def load_seen_ids(state_file: str) -> Set[int]:
    path = Path(state_file)
    if not path.exists():
        logger.info(f"Aucun fichier de state trouvé ({state_file}), on part de zéro")
        return set()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data.get("seen_ids", []))
    except Exception as e:
        logger.warning(f"Impossible de lire le fichier de state ({e}), on repart de zéro")
        return set()


def save_seen_ids(state_file: str, seen_ids: Set[int]) -> None:
    path = Path(state_file)
    path.write_text(
        json.dumps({"seen_ids": sorted(seen_ids)}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(f"State sauvegardé : {len(seen_ids)} annonce(s) connue(s)")
