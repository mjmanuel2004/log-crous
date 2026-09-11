"""Authentification MSE (MonEspaceEtudiant) sur trouverunlogement.lescrous.fr.

Le site fonctionne comme une SPA : les résultats de recherche ne sont visibles
qu'après connexion via un vrai navigateur (Selenium), pas via de simples
requêtes HTTP. C'est pour ça qu'on pilote un Chrome headless plutôt que
d'utiliser `requests` + BeautifulSoup seuls.

Le flux de login exact (URL, bouton intermédiaire) a déjà changé une fois côté
CROUS/MesServices depuis l'écriture du script original. Pour éviter de casser
à chaque changement de leur côté :
  - le clic sur le bouton intermédiaire est *optionnel* (certains flux sautent
    directement au formulaire user/password) ;
  - en cas d'échec à n'importe quelle étape, on sauvegarde une capture d'écran
    et le HTML de la page dans debug/, pour diagnostiquer sans deviner.
"""

import logging
from pathlib import Path
from time import monotonic, sleep

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.settings import Settings

settings = Settings()

logger = logging.getLogger(__name__)

DEBUG_DIR = Path("debug")


def dump_debug_info(driver: WebDriver, label: str) -> None:
    """Sauvegarde une capture d'écran + le HTML de la page courante dans debug/.
    Utile pour diagnostiquer un échec sans avoir à deviner la structure du site.
    """
    try:
        DEBUG_DIR.mkdir(exist_ok=True)
        screenshot_path = DEBUG_DIR / f"{label}.png"
        html_path = DEBUG_DIR / f"{label}.html"
        url_path = DEBUG_DIR / f"{label}_url.txt"

        driver.save_screenshot(str(screenshot_path))
        html_path.write_text(driver.page_source, encoding="utf-8")
        url_path.write_text(driver.current_url, encoding="utf-8")

        logger.error(
            f"Debug sauvegardé : {screenshot_path}, {html_path}, {url_path} "
            f"| titre de la page : {driver.title!r} "
            f"| taille du HTML : {len(driver.page_source)} caractères"
        )
    except Exception as dump_error:
        logger.error(f"Impossible de sauvegarder les infos de debug : {dump_error}")


class AuthenticationError(Exception):
    """Levée quand l'authentification échoue, après capture des infos de debug."""


class Authenticator:
    """Authentifie un WebDriver Selenium sur le site CROUS via MSE."""

    def __init__(self, email: str, password: str, delay: int = 2):
        self.email = email
        self.password = password
        self.delay = delay

    def authenticate_driver(self, driver: WebDriver) -> None:
        try:
            self._do_authenticate(driver)
        except Exception as e:
            dump_debug_info(driver, "authentication_failure")
            raise AuthenticationError(
                f"Échec de l'authentification MSE : {e}. "
                f"Voir les fichiers dans debug/ pour diagnostiquer "
                f"(page HTML + capture d'écran au moment de l'échec)."
            ) from e

    def _do_authenticate(self, driver: WebDriver) -> None:
        logger.info("Authentification sur le site CROUS...")

        # 1. Page de login
        logger.info(f"Ouverture de la page de login : {settings.MSE_LOGIN_URL}")
        driver.get(settings.MSE_LOGIN_URL)
        self._wait_for_page_ready(driver)

        # 2. Choisir la méthode d'authentification MSE, SI un bouton intermédiaire
        #    existe. Certains flux du site sautent directement au formulaire.
        mse_connect_button = self._find_first(
            driver,
            [
                (By.CLASS_NAME, "loginapp-button"),
                (By.XPATH, "//button[contains(translate(., 'CONEXIÉ', 'conexié'), 'connexion')]"),
                (By.XPATH, "//a[contains(translate(., 'CONEXIÉ', 'conexié'), 'connexion')]"),
            ],
        )
        if mse_connect_button:
            logger.info("Bouton intermédiaire trouvé, clic...")
            driver.execute_script("arguments[0].click();", mse_connect_button)
            self._wait_for_page_ready(driver)
        else:
            logger.info("Pas de bouton intermédiaire, on cherche directement le formulaire")

        # 3. Saisir les identifiants (plusieurs noms de champs possibles selon le flux)
        username_locators = [
            (By.NAME, "login[login]"),
            (By.ID, "login_login"),
            (By.NAME, "j_username"),
            (By.ID, "username"),
            (By.CSS_SELECTOR, "input[type='email']"),
            (By.CSS_SELECTOR, "input[name*='user']"),
        ]
        password_locators = [
            (By.NAME, "login[password]"),
            (By.ID, "login_password"),
            (By.NAME, "j_password"),
            (By.ID, "password"),
            (By.CSS_SELECTOR, "input[type='password']"),
        ]

        self._wait_for_any_locator(driver, username_locators, timeout=20, include_iframes=True)
        username_input = self._find_first(
            driver,
            username_locators,
            required=True,
            include_iframes=True,
        )
        password_input = self._find_first(
            driver,
            password_locators,
            required=True,
            include_iframes=True,
        )

        logger.info("Saisie des identifiants")
        username_input.send_keys(self.email)
        password_input.send_keys(self.password)

        self._solve_verification_if_present(driver)

        logger.info("Validation du formulaire de login")
        submit_button = self._find_first(
            driver,
            [
                (By.CSS_SELECTOR, "button[type='submit']"),
                (By.XPATH, "//button[contains(translate(., \"ABCDEFGHIJKLMNOPQRSTUVWXYZ\", \"abcdefghijklmnopqrstuvwxyz\"), \"identifier\")]"),
            ],
            include_iframes=True,
        )
        if submit_button:
            driver.execute_script("arguments[0].click();", submit_button)
        else:
            password_input.send_keys(Keys.RETURN)
        self._wait_for_page_ready(driver)

        # 3bis. Vérifier que le login a effectivement abouti. Sans ce contrôle,
        #       un mot de passe refusé ou un altcha non validé passe inaperçu :
        #       on enchaîne sur la suite et l'échec apparaît beaucoup plus loin,
        #       sous une forme incompréhensible.
        logger.info(f"URL après validation du formulaire : {driver.current_url}")
        if "login" in driver.current_url:
            dump_debug_info(driver, "login_not_completed")
            logger.warning(
                "Toujours sur une URL de login après soumission du formulaire : "
                "identifiants refusés, altcha non validé, ou étape supplémentaire. "
                "Voir debug/login_not_completed.*"
            )

        # 4. Valider le règlement, uniquement si explicitement demandé.
        #    Charger cette page laisse le navigateur incapable de naviguer
        #    ailleurs (toute navigation suivante timeoute sans changer d'URL),
        #    donc on ne la touche plus par défaut.
        if settings.VALIDATE_RULES:
            self._validate_rules(driver)
        else:
            logger.info("Étape règlement désactivée (VALIDATE_RULES=false)")

        # 5. Forcer la mise à jour du statut de connexion
        logger.info("Synchronisation du statut de connexion (mse/discovery/connect)")
        try:
            driver.get("https://trouverunlogement.lescrous.fr/mse/discovery/connect")
        except TimeoutException:
            logger.warning("Timeout sur mse/discovery/connect, on poursuit quand même")
        self._wait_for_page_ready(driver)

        logger.info(f"Authentification terminée, URL finale : {driver.current_url}")

    RULES_URL = "https://trouverunlogement.lescrous.fr/tools/36/rules"

    def _validate_rules(self, driver: WebDriver) -> None:
        logger.info(f"Vérification du règlement du site : {self.RULES_URL}")
        try:
            driver.get(self.RULES_URL)
        except TimeoutException:
            # On ne fait pas échouer tout le run ici : la page de règlement est
            # facultative si elle a déjà été acceptée une fois. On trace et on
            # continue, le parsing dira si l'accès aux annonces fonctionne.
            logger.warning(
                "Timeout au chargement de la page de règlement, on poursuit quand même"
            )
        self._wait_for_page_ready(driver)
        logger.info(f"URL après chargement du règlement : {driver.current_url}")

        validate_button = self._find_first(driver, [(By.NAME, "searchSubmit")])
        if validate_button:
            logger.info("Bouton de validation du règlement trouvé, clic")
            # Clic JS plutôt que natif : le clic natif de Selenium échoue si
            # l'élément est hors viewport ou recouvert (bandeau cookies), et
            # attend le rechargement complet de la page. Le reste du fichier
            # utilise déjà cette approche.
            driver.execute_script("arguments[0].click();", validate_button)
            self._wait_for_page_ready(driver)
            logger.info(f"Règlement validé, URL courante : {driver.current_url}")
        else:
            # Cas normal si le règlement a déjà été accepté, mais c'est aussi le
            # symptôme d'une redirection inattendue : on capture la page pour
            # pouvoir trancher au lieu de deviner.
            logger.info("Pas de bouton de règlement sur cette page")
            dump_debug_info(driver, "rules_page")

    def _find_first(
        self,
        driver: WebDriver,
        locators,
        required: bool = False,
        include_iframes: bool = False,
    ):
        for by, value in locators:
            try:
                el = driver.find_element(by, value)
                if el:
                    return el
            except NoSuchElementException:
                continue

        if include_iframes:
            driver.switch_to.default_content()
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                try:
                    driver.switch_to.default_content()
                    driver.switch_to.frame(iframe)
                except Exception:
                    continue

                for by, value in locators:
                    try:
                        el = driver.find_element(by, value)
                        if el:
                            return el
                    except NoSuchElementException:
                        continue

            driver.switch_to.default_content()

        if required:
            raise NoSuchElementException(
                f"Aucun des sélecteurs suivants n'a matché : {locators}"
            )
        return None

    def _wait_for_any_locator(
        self,
        driver: WebDriver,
        locators,
        timeout: int = 10,
        include_iframes: bool = False,
    ) -> None:
        deadline = monotonic() + timeout
        while monotonic() < deadline:
            if self._find_first(driver, locators, include_iframes=include_iframes):
                return
            sleep(0.5)

    def _solve_verification_if_present(self, driver: WebDriver) -> None:
        verify_checkbox = self._find_first(
            driver,
            [
                (By.CSS_SELECTOR, "altcha-widget input[type='checkbox']"),
                (By.CSS_SELECTOR, "input[id*='altcha'][type='checkbox']"),
            ],
        )
        if not verify_checkbox:
            return

        logger.info("Widget de vérification détecté, tentative de validation automatique")
        driver.execute_script("arguments[0].click();", verify_checkbox)

        try:
            WebDriverWait(driver, 20).until(
                lambda d: any(
                    widget.get_attribute("data-state") == "verified"
                    for widget in d.find_elements(By.CSS_SELECTOR, ".altcha")
                )
            )
            logger.info("Widget de vérification validé")
        except TimeoutException:
            logger.warning(
                "Widget de vérification non confirmé comme validé après 20s, on poursuit"
            )

    def _wait_for_page_ready(self, driver: WebDriver) -> None:
        try:
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            pass
        sleep(self.delay)
