import logging
import re
from time import sleep
from typing import List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from pydantic import HttpUrl
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.models import Accommodation, SearchResults

logger = logging.getLogger(__name__)


def extract_tool_id(search_url: str) -> str:
    """Extrait l'id d'outil dans une URL du type
    https://trouverunlogement.lescrous.fr/tools/47/search?... -> "47"
    """
    match = re.search(r"/tools/(\d+)/", urlparse(search_url).path + "/")
    return match.group(1) if match else "47"


class Parser:
    """Parse le site CROUS (déjà authentifié) pour extraire les annonces."""

    def __init__(self, authenticated_driver: WebDriver):
        self.driver = authenticated_driver

    # Deux signaux possibles que la SPA a fini de rendre : au moins une carte
    # d'annonce, ou le titre de résultats (présent même quand il n'y a aucune
    # annonce, avec le texte "Aucun...").
    RESULTS_LOCATOR = (By.CSS_SELECTOR, ".fr-card, .SearchResults-desktop")

    def get_accommodations(self, search_url: str) -> SearchResults:
        logger.info(f"Récupération des annonces pour : {search_url}")
        try:
            self.driver.get(str(search_url))
        except TimeoutException:
            # Le DOM est peut-être déjà exploitable malgré le timeout : on tente
            # le parsing plutôt que d'abandonner le run.
            logger.warning(
                "Timeout au chargement de la page de recherche, on tente quand même"
            )
        self._wait_for_results()
        logger.info(f"URL de la page parsée : {self.driver.current_url}")
        html = self.driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        num_accommodations = self._get_accommodations_count(soup)
        logger.info(f"{num_accommodations} annonce(s) trouvée(s)")

        return SearchResults(
            search_url=search_url,  # type: ignore
            count=num_accommodations,
            accommodations=parse_accommodations_summaries(soup),
        )

    def _wait_for_results(self, timeout: int = 30) -> None:
        """Attend que le JS ait réellement injecté les résultats dans le DOM.

        Avec page_load_strategy="eager", driver.get() rend la main dès que le
        HTML est parsé, avant que la SPA n'ait rendu quoi que ce soit. Un
        sleep(3) fixe serait un pari : trop court on parse une page vide et on
        conclut "0 annonce" à tort, trop long on ralentit chaque run pour rien.
        On attend donc un signal réel du DOM, avec un plafond.
        """
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(self.RESULTS_LOCATOR)
            )
            logger.info("Résultats rendus par la SPA")
        except TimeoutException:
            logger.warning(
                f"Aucun résultat rendu après {timeout}s. Soit la session n'est "
                f"pas authentifiée, soit la structure du site a changé."
            )
        # Petite marge : les cartes suivantes peuvent encore être en cours de
        # rendu au moment où la première apparaît.
        sleep(1)

    def _get_accommodations_count(self, soup: BeautifulSoup) -> Optional[int]:
        results_heading = soup.find(
            "h2", class_="SearchResults-desktop fr-h4 svelte-11sc5my"
        )

        if not results_heading:
            return None

        number_or_aucun = results_heading.text.split()[0]

        if number_or_aucun == "Aucun":
            return 0

        try:
            return int(number_or_aucun)
        except ValueError:
            return None


def _try_parse_url(title_card) -> str | None:
    try:
        return title_card.find("a")["href"]
    except Exception:
        return None


def _try_parse_id(url: str | None) -> int | None:
    if not url:
        return None
    try:
        return int(url.split("/")[-1])
    except Exception:
        return None


def _try_parse_image_url(image):
    if not image:
        return None
    try:
        return image["src"]
    except Exception:
        return None


def _try_parse_price(price) -> float | str | None:
    if not price:
        return None
    try:
        return float(price.text.strip().strip("€").strip().replace(",", "."))
    except Exception:
        pass
    return price.text.strip()


def parse_accommodation_card(card: BeautifulSoup) -> Accommodation | None:
    title_card = card.find("h3", class_="fr-card__title")
    if not title_card:
        return None

    title = title_card.text.strip()
    url = _try_parse_url(title_card)
    accommodation_id = _try_parse_id(url)

    image = card.find("img", class_="fr-responsive-img")
    image_url = _try_parse_image_url(image)

    overview_details = []

    address = card.find("p", class_="fr-card__desc")
    if address:
        overview_details.append(address.text.strip())

    details = card.find_all("p", class_="fr-card__detail")
    for detail in details:
        overview_details.append(detail.text.strip())

    price = card.find("p", class_="fr-badge")
    price = _try_parse_price(price)

    return Accommodation(
        id=accommodation_id,
        title=title,
        image_url=image_url,  # type: ignore
        price=price,
        overview_details="\n".join(overview_details),
    )


def parse_accommodations_summaries(soup: BeautifulSoup) -> List[Accommodation]:
    cards = soup.find_all("div", class_="fr-card")

    accommodations: List[Accommodation] = []
    for card in cards:
        accommodation = parse_accommodation_card(card)
        if accommodation:
            accommodations.append(accommodation)

    return accommodations
