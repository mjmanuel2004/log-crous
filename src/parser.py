import logging
import re
from time import sleep
from typing import List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from pydantic import HttpUrl
from selenium.webdriver.chrome.webdriver import WebDriver

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

    def get_accommodations(self, search_url: str) -> SearchResults:
        logger.info(f"Récupération des annonces pour : {search_url}")
        self.driver.get(str(search_url))
        sleep(3)  # laisser le temps au JS de charger les résultats
        html = self.driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        num_accommodations = self._get_accommodations_count(soup)
        logger.info(f"{num_accommodations} annonce(s) trouvée(s)")

        return SearchResults(
            search_url=search_url,  # type: ignore
            count=num_accommodations,
            accommodations=parse_accommodations_summaries(soup),
        )

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
