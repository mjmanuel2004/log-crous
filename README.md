# Alerte logement CROUS Rennes

Surveille automatiquement les nouvelles annonces sur `trouverunlogement.lescrous.fr`
pour la zone de Rennes et envoie un email dès qu'une nouvelle annonce apparaît.

Tourne gratuitement via **GitHub Actions** (cron toutes les 15 min), pas besoin de
laisser un PC allumé.

## Comment ça marche

1. Un Chrome headless se connecte au site avec tes identifiants MonEspaceÉtudiant (MSE).
2. Il charge la page de recherche Rennes et récupère la liste des annonces visibles.
3. Le script compare avec `seen_ids.json` (les annonces déjà vues lors des runs précédents).
4. S'il y a du nouveau → email envoyé, uniquement pour les nouvelles annonces.
5. `seen_ids.json` est mis à jour et recommité automatiquement dans le repo.

## Mise en place (10-15 min)

### 1. Créer le repo GitHub

Crée un nouveau repo **privé** (pour ne pas exposer ton URL de recherche
publiquement) sur GitHub, et pousse ce dossier dedans :

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <URL_DE_TON_REPO>
git push -u origin main
```

### 2. Générer un mot de passe d'application Gmail

- Va dans ton compte Google > Sécurité
- Active la validation en 2 étapes si ce n'est pas déjà fait (obligatoire pour l'étape suivante)
- Va dans "Mots de passe des applications", génère-en un pour "Mail"
- Garde le code à 16 caractères généré, c'est ta valeur `GMAIL_APP_PASSWORD`

### 3. Configurer les secrets du repo

Dans ton repo GitHub : **Settings > Secrets and variables > Actions > New repository secret**.
Ajoute ces 6 secrets :

| Nom | Valeur |
|---|---|
| `MSE_EMAIL` | ton email MonEspaceÉtudiant |
| `MSE_PASSWORD` | ton mot de passe MSE |
| `SEARCH_URL` | `https://trouverunlogement.lescrous.fr/tools/47/search?bounds=-1.7525876_48.1549705_-1.6244045_48.0769155&locationName=Rennes` |
| `GMAIL_ADDRESS` | l'adresse Gmail qui enverra les emails |
| `GMAIL_APP_PASSWORD` | le mot de passe d'application généré à l'étape 2 |
| `NOTIFY_EMAIL_TO` | l'adresse qui doit recevoir les alertes (peut être la même que `GMAIL_ADDRESS`) |

### 4. Activer le workflow

Le workflow se déclenche automatiquement toutes les 15 min une fois poussé sur `main`.
Tu peux aussi le lancer manuellement pour tester : onglet **Actions** du repo →
"Surveillance logement CROUS Rennes" → **Run workflow**.

### 5. Vérifier que ça marche

Regarde les logs dans l'onglet **Actions**. Si la connexion MSE ou le parsing
échoue, c'est visible directement dans les logs du step "Lancer le script de
surveillance".

## Tester en local avant de déployer (optionnel mais recommandé)

```bash
cp .env.template .env
# remplis .env avec tes vraies valeurs
pip install -r requirements.txt
python main.py
```

## Points d'attention

- **Structure du site** : le parsing se base sur les classes CSS actuelles du
  site (`fr-card`, `fr-card__title`, etc.). Si le CROUS refait son site, le
  parsing peut casser — dans ce cas, il faudra ajuster `src/parser.py`.
- **Fréquence** : 15 min est un bon compromis. Descendre en dessous de 5 min
  n'est pas garanti par GitHub Actions et sollicite inutilement le site.
- **Inactivité du repo** : GitHub désactive les workflows planifiés après
  60 jours sans activité sur le repo. Un simple commit de temps en temps
  suffit à réactiver (le commit automatique de `seen_ids.json` compte
  généralement comme de l'activité, mais surveille quand même).
- **Confidentialité** : garde le repo **privé** puisqu'il référence ta
  recherche personnelle, même si les identifiants eux-mêmes ne sont jamais
  dans le code (uniquement dans les Secrets, jamais committés).
