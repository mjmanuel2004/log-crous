"""Configuration centralisée, chargée depuis les variables d'environnement
(ou un fichier .env en local). En production (GitHub Actions), ces valeurs
viennent des Secrets du repo.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- Connexion CROUS (MonEspaceEtudiant) --
    MSE_LOGIN_URL: str = "https://messervices.etudiant.gouv.fr/oauth2/login"
    MSE_EMAIL: str = Field(default=...)
    MSE_PASSWORD: str = Field(default=...)

    # -- URL de recherche à surveiller --
    # Doit correspondre au format https://trouverunlogement.lescrous.fr/tools/<id>/search?bounds=...
    SEARCH_URL: str = Field(default=...)

    # -- Envoi d'email (Gmail SMTP) --
    GMAIL_ADDRESS: str = Field(default=...)
    GMAIL_APP_PASSWORD: str = Field(default=...)  # mot de passe d'application, pas le mot de passe du compte
    NOTIFY_EMAIL_TO: str = Field(default=...)  # peut être la même adresse que GMAIL_ADDRESS

    # -- Fichier de state (IDs d'annonces déjà notifiées) --
    STATE_FILE: str = "seen_ids.json"
