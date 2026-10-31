"""
telegram_alerts_signal10.py
=============================
Alertas Telegram para la Estrategia #10 (señal ML). Mismo patrón que el
telegram_alerts.py ya construido para Stat Arb: credenciales SOLO desde
variables de entorno, nunca hardcodeadas; fallo de red no rompe el script
principal (devuelve False, no lanza excepción).

A diferencia del bot de Stat Arb (que alerta sobre oportunidades de trading),
este bot tiene un propósito distinto y más limitado, alineado con la decisión
de mantener la señal dentro del paper trading lab: alerta SOLO sobre FALLOS
de ejecución del pipeline diario (datos no disponibles, error de modelo,
etc.), no sobre las señales de trading en sí. Esto es deliberado -- ya se
decidió que esta estrategia no debe influir en decisiones de capital real
todavía, así que no tiene sentido generar urgencia con alertas de "señal
alcista en NVDA" que podrían tentar a actuar fuera del lab.

Setup previo (si no se hizo ya para Stat Arb -- mismas credenciales se
reutilizan, es el mismo bot):
  1. Crear bot con @BotFather en Telegram, obtener token
  2. Obtener chat_id enviando un mensaje al bot y consultando getUpdates
  3. Guardar ambos en strategy-lab/.env (no en este archivo) -- lo hace
     scripts/setup_telegram.ps1. Si existen como variables de entorno,
     tienen prioridad sobre el .env:
       TELEGRAM_BOT_TOKEN
       TELEGRAM_CHAT_ID
"""

import os
import logging
import urllib.request
import urllib.parse
import json
import html
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # sin python-dotenv solo valen las variables de entorno
    load_dotenv = None

# override=False: una variable de entorno ya definida gana al .env
if load_dotenv is not None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

# Va al daily_signal_run.log vía el root logger: con print() los avisos de
# dry-run se perdían bajo Task Scheduler (nadie captura stdout).
logger = logging.getLogger(__name__)


def send_telegram_message(text: str) -> bool:
    """
    Envía un mensaje vía la API de Telegram Bot.
    Retorna True si el envío fue exitoso, False en caso contrario (sin
    lanzar excepción, para que un fallo de red no rompa el run diario).
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        logger.warning("[telegram] TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no configurados "
                       "-- alerta no enviada (modo dry-run). Mensaje:\n%s", text)
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}

    try:
        data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
            return bool(result.get("ok", False))
    except Exception as e:
        logger.error("[telegram] Error enviando alerta Telegram: %s", e)
        return False


def alert_pipeline_failure(ticker: str, stage: str, error_message: str) -> None:
    """
    Alerta específica para un fallo en una etapa concreta del pipeline diario.

    Las variables dinámicas se escapan con html.escape() antes de insertarse
    en el mensaje: con parse_mode="HTML", un error_message que contenga
    caracteres como '<' o '&' (frecuente en excepciones de pandas/numpy,
    ej. "<NA>") rompería el parseo en Telegram y el envío fallaría
    silenciosamente -- justo en el caso en que la alerta más importa.
    """
    text = (
        f"⚠️ <b>Estrategia 10 (ML Signal) — Fallo en pipeline diario</b>\n\n"
        f"Activo: {html.escape(ticker)}\n"
        f"Etapa: {html.escape(stage)}\n"
        f"Error: {html.escape(error_message)}\n\n"
        f"Ver log local para detalle completo."
    )
    send_telegram_message(text)


def alert_pipeline_summary_if_partial_failure(n_success: int, n_total: int, failed_tickers: list) -> None:
    """
    Alerta de resumen SOLO si hubo al menos un fallo parcial -- no se envía
    nada si todo corrió bien, para no generar ruido de notificaciones diarias
    sin valor (el log local ya registra el éxito).
    """
    if not failed_tickers:
        return  # todo OK, no hace falta alertar

    text = (
        f"⚠️ <b>Estrategia 10 — Ejecución parcial</b>\n\n"
        f"Completados: {n_success}/{n_total} activos\n"
        f"Fallaron: {html.escape(', '.join(failed_tickers))}\n\n"
        f"Revisar log local para diagnóstico."
    )
    send_telegram_message(text)
