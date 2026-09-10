import logging
import os

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.webdriver import WebDriver

from src.authenticator import Authenticator, dump_debug_info
from src.email_notifier import EmailNotifier
from src.parser import Parser, extract_tool_id
from src.settings import Settings
from src.state import load_seen_ids, save_seen_ids

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
    level=logging.INFO,
)
logger = logging.getLogger("crous_watch")


def create_driver(headless: bool = True) -> WebDriver:
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")

    # Si CHROME_PATH est défini (ex: fourni par browser-actions/setup-chrome
    # dans le workflow GitHub Actions), on l'indique explicitement à Selenium.
    # Sans ça, Selenium Manager peut ne pas trouver le binaire Chrome installé
    # dans un emplacement non standard, et lever une erreur au démarrage.
    chrome_path = os.environ.get("CHROME_PATH")
    if chrome_path:
        logger.info(f"Utilisation du binaire Chrome explicite : {chrome_path}")
        chrome_options.binary_location = chrome_path

    return webdriver.Chrome(options=chrome_options)


def main() -> None:
    settings = Settings()

    driver = create_driver(headless=True)

    try:
        Authenticator(settings.MSE_EMAIL, settings.MSE_PASSWORD).authenticate_driver(
            driver
        )

        parser = Parser(driver)
        try:
            search_results = parser.get_accommodations(settings.SEARCH_URL)
        except Exception as e:
            dump_debug_info(driver, "parsing_failure")
            raise

        current_ids = {
            acc.id for acc in search_results.accommodations if acc.id is not None
        }
        seen_ids = load_seen_ids(settings.STATE_FILE)

        new_ids = current_ids - seen_ids
        new_accommodations = [
            acc for acc in search_results.accommodations if acc.id in new_ids
        ]

        if new_accommodations:
            logger.info(f"{len(new_accommodations)} nouvelle(s) annonce(s) détectée(s) !")
            tool_id = extract_tool_id(settings.SEARCH_URL)
            notifier = EmailNotifier(
                gmail_address=settings.GMAIL_ADDRESS,
                gmail_app_password=settings.GMAIL_APP_PASSWORD,
                to_address=settings.NOTIFY_EMAIL_TO,
            )
            notifier.send_new_accommodations(
                new_accommodations, tool_id, settings.SEARCH_URL
            )
        else:
            logger.info("Aucune nouvelle annonce depuis la dernière vérification.")

        # On mémorise TOUTES les annonces actuellement visibles (pas seulement
        # les nouvelles), pour ne jamais re-notifier une annonce déjà vue.
        save_seen_ids(settings.STATE_FILE, seen_ids | current_ids)

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
