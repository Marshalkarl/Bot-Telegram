# 🤖 Bot Telegram



Un bot Telegram en Python : météo et prévisions, rappels uniques ou quotidiens (persistés en SQLite), fuseau horaire par utilisateur, tests automatiques et configuration de déploiement.

## Fonctionnalités

| Commande | Description |
|---|---|
| `/start` | Message de bienvenue |
| `/aide` | Liste des commandes |
| `/de` | Lance un dé |
| `/blague` | Blague aléatoire |
| `/meteo <ville>` | Météo actuelle |
| `/prevision <ville>` | Prévisions sur 5 jours |
| `/rappel <minutes> <message>` | Rappel unique |
| `/quotidien <heure> <message>` | Rappel tous les jours (`8h`, `8h30`, `08:30`) |
| `/rappels` | Liste tes rappels en attente |
| `/annuler <id>` | Annule un rappel (unique ou quotidien) |
| `/fuseau <zone>` | Règle ton fuseau horaire (ex. `Africa/Lome`) |

Les rappels sont enregistrés dans SQLite et rechargés automatiquement au redémarrage. Les rappels quotidiens suivent ton fuseau horaire : si tu le changes avec `/fuseau`, ils sont reprogrammés. Les noms de fuseaux viennent de la [liste IANA](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).

## Structure

```
bot.py               # Point d'entrée et commandes
db.py                # SQLite : rappels et fuseaux
weather.py           # Appels à l'API météo
utils.py             # Fonctions pures (heures, fuseaux, prévisions)
tests/               # Tests pytest
.github/workflows/   # CI GitHub Actions
Dockerfile, Procfile, render.yaml   # Déploiement
```

## Installation locale

1. Crée un bot avec [@BotFather](https://t.me/BotFather) (`/newbot`) et copie le token.
2. Crée un compte gratuit sur [OpenWeatherMap](https://openweathermap.org/api) et copie ta clé API (elle peut mettre quelques minutes à s'activer).
3. Installe le projet :

```bash
git clone https://github.com/<ton-pseudo>/telegram-bot.git
cd telegram-bot
python -m venv venv
source venv/bin/activate   # Windows : venv\Scripts\activate
pip install -r requirements.txt
```

4. Copie `.env.example` en `.env` et remplis les clés.
5. Lance le bot :

```bash
python bot.py
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

La CI GitHub Actions lance automatiquement les tests (Python 3.11 et 3.12) à chaque push et pull request. Pense à remplacer `<ton-pseudo>` dans le badge en haut de ce fichier.

## Déploiement

Le bot utilise le *polling* : il n'a besoin d'aucun port ouvert, seulement d'un processus qui tourne en continu.

- **Railway** : connecte le dépôt GitHub, ajoute les variables `TELEGRAM_TOKEN` et `OPENWEATHER_API_KEY`.
- **Render** : crée un *Background Worker* depuis le dépôt (le `render.yaml` est pris en compte) et renseigne les variables d'environnement.
- **Docker** :

```bash
docker build -t telegram-bot .
docker run -d --env-file .env -v bot-data:/data -e DB_PATH=/data/bot.db telegram-bot
```

> ⚠️ Sur la plupart des hébergeurs, le disque est **éphémère** : sans volume persistant, la base SQLite est effacée à chaque redéploiement, et avec elle les rappels et les fuseaux. Monte un volume et pointe `DB_PATH` dessus pour les conserver.

## Idées d'amélioration

- Rappels hebdomadaires (`/hebdo lundi 9h ...`)
- Localisation automatique du fuseau via la position Telegram
- Passer de SQLite à PostgreSQL pour un hébergement sans volume
- Lint avec Ruff dans la CI


