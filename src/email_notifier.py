"""Envoi d'email via le SMTP de Gmail.

Nécessite un "mot de passe d'application" Google (pas le mot de passe du
compte) : à générer dans Compte Google > Sécurité > Validation en 2 étapes
> Mots de passe des applications.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

from src.models import Accommodation

logger = logging.getLogger(__name__)

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587


class EmailNotifier:
    def __init__(self, gmail_address: str, gmail_app_password: str, to_address: str):
        self.gmail_address = gmail_address
        self.gmail_app_password = gmail_app_password
        self.to_address = to_address

    def send_new_accommodations(
        self, new_accommodations: List[Accommodation], tool_id: str, search_url: str
    ) -> None:
        if not new_accommodations:
            return

        subject = f"🏠 {len(new_accommodations)} nouvelle(s) annonce(s) CROUS Rennes !"
        body = self._build_body(new_accommodations, tool_id, search_url)

        self._send(subject, body)

    def _build_body(
        self, accommodations: List[Accommodation], tool_id: str, search_url: str
    ) -> str:
        lines = ["Nouvelles annonces disponibles :", ""]

        for acc in accommodations:
            price = f"{acc.price}€" if isinstance(acc.price, float) else acc.price
            link = f"https://trouverunlogement.lescrous.fr/tools/{tool_id}/accommodations/{acc.id}"
            lines.append(f"- {acc.title} ({price})")
            if acc.overview_details:
                lines.append(f"  {acc.overview_details}")
            lines.append(f"  {link}")
            lines.append("")

        lines.append(f"Recherche complète : {search_url}")
        lines.append("")
        lines.append("⚡ Les annonces CROUS partent vite, va vite jeter un œil !")

        return "\n".join(lines)

    def _send(self, subject: str, body: str) -> None:
        msg = MIMEMultipart()
        msg["From"] = self.gmail_address
        msg["To"] = self.to_address
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        logger.info(f"Envoi de l'email à {self.to_address}...")
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(self.gmail_address, self.gmail_app_password)
            server.send_message(msg)
        logger.info("Email envoyé.")
