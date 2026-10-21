import logging
import os
import random
import time
from datetime import datetime
from datetime import time as dtime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import db
from utils import parse_time, valid_timezone
from weather import WeatherError, get_forecast, get_weather

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)  # évite de logger le token dans les URLs
logger = logging.getLogger(__name__)

BLAGUES = [
    "Pourquoi les plongeurs plongent-ils toujours en arrière ? Parce que sinon ils tomberaient dans le bateau.",
    "Que dit un escargot sur le dos d'une tortue ? Youpiii !",
    "Quel est le comble pour un électricien ? De ne pas être au courant.",
]

COMMANDES = [
    ("start", "Démarrer le bot"),
    ("aide", "Afficher l'aide"),
    ("de", "Lancer un dé"),
    ("blague", "Une blague au hasard"),
    ("meteo", "Météo d'une ville : /meteo Lomé"),
    ("prevision", "Prévisions sur 5 jours : /prevision Lomé"),
    ("rappel", "Rappel unique : /rappel 10 boire de l'eau"),
    ("quotidien", "Rappel quotidien : /quotidien 8h30 vitamines"),
    ("rappels", "Voir mes rappels"),
    ("annuler", "Annuler un rappel : /annuler 3"),
    ("fuseau", "Régler mon fuseau : /fuseau Africa/Lome"),
]


def tz_of(chat_id: int) -> str:
    return db.get_timezone(chat_id) or "UTC"


# ---------- Commandes de base ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prenom = update.effective_user.first_name
    await update.message.reply_text(
        f"Salut {prenom} ! Je suis ton bot. Tape /aide pour voir mes commandes.\n"
        "Astuce : règle ton fuseau horaire avec /fuseau Africa/Lome pour que "
        "tes rappels tombent à la bonne heure."
    )


async def aide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lignes = [f"/{nom} - {description}" for nom, description in COMMANDES]
    await update.message.reply_text("Commandes disponibles :\n" + "\n".join(lignes))


async def de(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🎲 Tu as obtenu : {random.randint(1, 6)}")


async def blague(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(BLAGUES))


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Tu as dit : {update.message.text}")


# ---------- Météo ----------

async def meteo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage : /meteo Lomé")
        return
    try:
        texte = await get_weather(" ".join(context.args))
    except WeatherError as e:
        texte = f"⚠️ {e}"
    await update.message.reply_text(texte)


async def prevision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage : /prevision Lomé")
        return
    try:
        texte = await get_forecast(" ".join(context.args))
    except WeatherError as e:
        texte = f"⚠️ {e}"
    await update.message.reply_text(texte)


# ---------- Rappels (persistés en base SQLite) ----------

def retirer_jobs(job_queue, reminder_id: int):
    for job in job_queue.get_jobs_by_name(f"rappel_{reminder_id}"):
        job.schedule_removal()


async def envoyer_rappel(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    await context.bot.send_message(job.chat_id, f"⏰ Rappel : {job.data['text']}")
    db.delete_reminder(job.data["id"])


async def envoyer_rappel_quotidien(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    await context.bot.send_message(job.chat_id, f"🔁 Rappel : {job.data['text']}")


def planifier(job_queue, reminder_id: int, chat_id: int, text: str, due_ts: float):
    """Programme un rappel unique (immédiat s'il est déjà en retard)."""
    job_queue.run_once(
        envoyer_rappel,
        when=max(0, due_ts - time.time()),
        chat_id=chat_id,
        name=f"rappel_{reminder_id}",
        data={"id": reminder_id, "text": text},
    )


def planifier_quotidien(job_queue, reminder_id: int, chat_id: int, text: str, hhmm: str):
    """Programme un rappel tous les jours à HH:MM, dans le fuseau de l'utilisateur."""
    heure, minute = map(int, hhmm.split(":"))
    tz = ZoneInfo(tz_of(chat_id))
    job_queue.run_daily(
        envoyer_rappel_quotidien,
        time=dtime(heure, minute, tzinfo=tz),
        chat_id=chat_id,
        name=f"rappel_{reminder_id}",
        data={"id": reminder_id, "text": text},
    )


async def rappel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        minutes = float(context.args[0].replace(",", "."))
        texte = " ".join(context.args[1:])
        if not texte or minutes <= 0:
            raise ValueError
    except (IndexError, ValueError):
        await update.message.reply_text("Usage : /rappel 10 boire de l'eau")
        return

    chat_id = update.effective_chat.id
    reminder_id, due_ts = db.add_reminder(chat_id, texte, minutes)
    planifier(context.job_queue, reminder_id, chat_id, texte, due_ts)
    await update.message.reply_text(
        f"C'est noté (#{reminder_id}), je te rappelle dans {minutes:g} min."
    )


async def quotidien(update: Update, context: ContextTypes.DEFAULT_TYPE):
    horaire = parse_time(context.args[0]) if context.args else None
    texte = " ".join(context.args[1:])
    if not horaire or not texte:
        await update.message.reply_text("Usage : /quotidien 8h30 prendre mes vitamines")
        return

    chat_id = update.effective_chat.id
    hhmm = f"{horaire[0]:02d}:{horaire[1]:02d}"
    reminder_id = db.add_daily(chat_id, texte, hhmm)
    planifier_quotidien(context.job_queue, reminder_id, chat_id, texte, hhmm)

    reponse = f"C'est noté (#{reminder_id}) : tous les jours à {hhmm} ({tz_of(chat_id)})."
    if db.get_timezone(chat_id) is None:
        reponse += "\nTon fuseau n'est pas réglé (UTC par défaut) : utilise /fuseau Africa/Lome"
    await update.message.reply_text(reponse)


async def rappels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    items = db.get_chat_reminders(chat_id)
    if not items:
        await update.message.reply_text("Tu n'as aucun rappel en attente.")
        return

    tz_name = tz_of(chat_id)
    tz = ZoneInfo(tz_name)
    lignes = []
    for rid, texte, due, daily in items:
        if daily:
            lignes.append(f"#{rid} - 🔁 tous les jours à {daily} : {texte}")
        else:
            quand = datetime.fromtimestamp(due, tz).strftime("%d/%m %H:%M")
            lignes.append(f"#{rid} - {quand} : {texte}")
    await update.message.reply_text(f"Tes rappels (fuseau {tz_name}) :\n" + "\n".join(lignes))


async def annuler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        reminder_id = int(context.args[0].lstrip("#"))
    except (IndexError, ValueError):
        await update.message.reply_text("Usage : /annuler 3")
        return

    if not db.delete_reminder(reminder_id, update.effective_chat.id):
        await update.message.reply_text("Rappel introuvable.")
        return

    retirer_jobs(context.job_queue, reminder_id)
    await update.message.reply_text(f"Rappel #{reminder_id} annulé.")


async def fuseau(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        actuel = db.get_timezone(chat_id) or "UTC (par défaut)"
        await update.message.reply_text(
            f"Fuseau actuel : {actuel}\nPour le changer : /fuseau Africa/Lome"
        )
        return

    nom = context.args[0]
    if not valid_timezone(nom):
        await update.message.reply_text(
            "Fuseau inconnu. Utilise un nom du type Africa/Lome, Europe/Paris ou America/Montreal."
        )
        return

    db.set_timezone(chat_id, nom)
    # Les rappels quotidiens doivent être reprogrammés dans le nouveau fuseau
    for rid, texte, _due, daily in db.get_chat_reminders(chat_id):
        if daily:
            retirer_jobs(context.job_queue, rid)
            planifier_quotidien(context.job_queue, rid, chat_id, texte, daily)
    await update.message.reply_text(f"Fuseau réglé sur {nom}. Tes rappels quotidiens sont à jour.")


# ---------- Démarrage ----------

async def au_demarrage(app: Application):
    """Publie le menu des commandes et reprogramme les rappels sauvegardés."""
    await app.bot.set_my_commands([BotCommand(nom, desc) for nom, desc in COMMANDES])

    pending = db.get_all_reminders()
    for rid, chat_id, texte, due_ts, daily in pending:
        if daily:
            planifier_quotidien(app.job_queue, rid, chat_id, texte, daily)
        else:
            planifier(app.job_queue, rid, chat_id, texte, due_ts)
    logger.info("%d rappel(s) rechargé(s) depuis la base", len(pending))


def main():
    if not TOKEN:
        raise SystemExit("TELEGRAM_TOKEN manquant : crée un fichier .env")

    db.init_db()

    app = Application.builder().token(TOKEN).post_init(au_demarrage).build()
    for nom, fonction in [
        ("start", start),
        ("aide", aide),
        ("de", de),
        ("blague", blague),
        ("meteo", meteo),
        ("prevision", prevision),
        ("rappel", rappel),
        ("quotidien", quotidien),
        ("rappels", rappels),
        ("annuler", annuler),
        ("fuseau", fuseau),
    ]:
        app.add_handler(CommandHandler(nom, fonction))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    logger.info("Bot démarré...")
    app.run_polling()


if __name__ == "__main__":
    main()
