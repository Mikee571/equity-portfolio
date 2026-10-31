"""
Alertas Telegram para Stat Arb
================================
Capa de notificación sobre stat_arb_pairs.py. Envía una alerta a Telegram
SOLO cuando:
  1. El par pasó la validación de dos etapas (Engle-Granger + Johansen)
  2. El z-score actual supera el umbral de entrada (±1.5σ por default)

Esto es deliberado: no alertamos sobre divergencias tácticas (ej. XOM/AAL,
que no está cointegrado) para no entrenar el hábito de actuar sobre señales
sin ancla estadística real. Si se quiere monitorear también las tácticas,
hay que pedirlo explícitamente — no es el comportamiento default.

Setup previo:
  1. Crear bot con @BotFather en Telegram, obtener token
  2. Obtener chat_id enviando un mensaje al bot y consultando getUpdates
  3. Guardar ambos en strategy-lab/.env (no en este archivo) -- lo hace
     scripts/setup_telegram.ps1. Si existen como variables de entorno,
     tienen prioridad sobre el .env:
       TELEGRAM_BOT_TOKEN
       TELEGRAM_CHAT_ID

Uso: python telegram_alerts.py
"""

import os
import urllib.request
import urllib.parse
import json
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # sin python-dotenv solo valen las variables de entorno
    load_dotenv = None

# override=False: una variable de entorno ya definida gana al .env
if load_dotenv is not None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

# Importamos las funciones ya construidas y validadas en semanas anteriores
from stat_arb_pairs import (
    PAIRS, PERIOD, INTERVAL, ZSCORE_ENTRY, ZSCORE_EXIT,
    fetch_pair_data, engle_granger_test, hedge_ratio_ols,
    compute_spread_zscore, johansen_test, half_life_reversion,
)

import numpy as np


def send_telegram_message(text: str) -> bool:
    """
    Envía un mensaje vía la API de Telegram Bot.
    Lee las credenciales de variables de entorno — nunca hardcodeadas.
    Retorna True si el envío fue exitoso, False en caso contrario
    (sin lanzar excepción, para que un fallo de red no rompa el scan diario).
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("⚠ TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no configurados.")
        print("  El mensaje se imprime aquí en vez de enviarse:")
        print(f"  {text}")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }

    try:
        data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("ok", False)
    except Exception as e:
        print(f"⚠ Error enviando a Telegram: {e}")
        print(f"  Mensaje no enviado: {text}")
        return False


def format_alert(pair_name: str, ticker_y: str, ticker_x: str, current_z: float,
                  half_life: float, beta: float) -> str:
    """Formatea el mensaje de alerta con la dirección sugerida del trade."""
    direction = (
        f"CORTO {ticker_y} / LARGO {ticker_x}" if current_z > 0
        else f"LARGO {ticker_y} / CORTO {ticker_x}"
    )
    half_life_str = f"{half_life:.1f} días" if half_life else "N/A"

    return (
        f"🔔 *Señal Stat Arb — {pair_name}*\n\n"
        f"Z-score: `{current_z:.2f}`\n"
        f"Dirección sugerida: {direction}\n"
        f"Hedge ratio (beta, log): `{beta:.4f}`\n"
        f"Half-life de reversión: {half_life_str}\n\n"
        f"_Par validado por Engle-Granger + Johansen._\n"
        f"_{datetime.now().strftime('%Y-%m-%d %H:%M')}_"
    )


def check_pairs_and_alert(dry_run: bool = False) -> list:
    """
    Recorre todos los pares definidos en PAIRS, valida cointegración con
    las dos etapas (EG + Johansen), y envía alerta SOLO si:
      - el par está validado como COINTEGRADO (ambos tests coinciden)
      - el z-score actual supera ZSCORE_ENTRY

    dry_run=True imprime el mensaje en consola sin enviarlo a Telegram —
    útil para probar el formato antes de tener credenciales configuradas.
    """
    alerts_sent = []

    print(f"CHEQUEO DE ALERTAS STAT ARB — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    for name, cfg in PAIRS.items():
        ticker_y, ticker_x = cfg["y"], cfg["x"]
        print(f"\n{name}...")

        try:
            data = fetch_pair_data(ticker_y, ticker_x)
        except Exception as e:
            print(f"  Error descargando datos: {e}")
            continue

        if len(data) < 60:
            print(f"  Datos insuficientes ({len(data)} filas)")
            continue

        y, x = data["y"], data["x"]

        eg_score, eg_pvalue = engle_granger_test(y, x, use_log=True)
        eg_cointegrated = eg_pvalue < 0.05

        trace_stat, crit_val_95, johansen_cointegrated = johansen_test(y, x, use_log=True)

        if eg_cointegrated and johansen_cointegrated:
            verdict = "COINTEGRADO"
        elif eg_cointegrated or johansen_cointegrated:
            verdict = "AMBIGUO"
        else:
            verdict = "NO COINTEGRADO"

        is_cointegrated = verdict == "COINTEGRADO"

        beta = hedge_ratio_ols(y, x, use_log=True)
        log_y, log_x = np.log(y), np.log(x)
        spread, zscore = compute_spread_zscore(log_y, log_x, beta, window=30)
        current_z = zscore.iloc[-1]

        half_life, _ = half_life_reversion(spread) if is_cointegrated else (None, None)

        print(f"  Veredicto: {verdict}  |  Z-score actual: {current_z:.2f}")

        if not is_cointegrated:
            print(f"  → Sin alerta: el par no está validado como Stat Arb "
                  f"(veredicto={verdict}), independientemente del z-score.")
            continue

        if abs(current_z) >= ZSCORE_ENTRY:
            message = format_alert(name, ticker_y, ticker_x, current_z, half_life, beta)
            if dry_run:
                print(f"  🔔 ALERTA (dry-run, no enviada):\n{message}")
                sent = True
            else:
                sent = send_telegram_message(message)
                print(f"  {'✓ Alerta enviada' if sent else '✗ Fallo al enviar alerta'}")

            alerts_sent.append({
                "pair": name, "zscore": current_z, "verdict": verdict, "sent": sent
            })
        else:
            print(f"  → Sin alerta: |z|={abs(current_z):.2f} no supera el umbral "
                  f"({ZSCORE_ENTRY})")

    print(f"\n{'='*70}")
    print(f"Total alertas disparadas: {len(alerts_sent)}")
    return alerts_sent


if __name__ == "__main__":
    has_credentials = bool(os.environ.get("TELEGRAM_BOT_TOKEN")) and bool(os.environ.get("TELEGRAM_CHAT_ID"))
    if not has_credentials:
        print("ℹ TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID no detectados — corriendo en modo dry-run.\n")
    check_pairs_and_alert(dry_run=not has_credentials)
