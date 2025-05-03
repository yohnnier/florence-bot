# ── imports ────────────────────────────────────────────
import os
import time
import threading
import logging
import sys

from flask import Flask, request, abort
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client as TwilioRest
from openai import OpenAI

# ── configuración de logging ───────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("florence-bot")

# ── Flask ──────────────────────────────────────────────
app = Flask(__name__)

# ── OpenAI client (SDK v2 + Assistants v2) ─────────────
openai_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    default_headers={"OpenAI-Beta": "assistants=v2"},
)
ASSISTANT_ID = os.getenv("ASSISTANT_ID")

# ── Twilio REST (para la respuesta asíncrona) ──────────
twilio_rest = TwilioRest(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN"),
)
TWILIO_FROM = "whatsapp:+13158123738"        # tu sandbox / número verificado
MAX_LEN = 1500                               # margen de seguridad (< 1600)

# ───────────────────────────────────────────────────────
@app.get("/")
def home():
    return "Florence bot en línea 🚀"

# ---------- webhook (ACK inmediato) -------------------
@app.post("/webhook")
def webhook():
    incoming = request.values.get("Body", "").strip()
    from_number = request.values.get("From")

    if not incoming:
        abort(400, "mensaje vacío")

    # 1. ACK rápido
    twiml = MessagingResponse()
    twiml.message("✔️ Recibido, dame unos segundos…")

    # 2. procesar en segundo plano
    threading.Thread(
        target=wait_and_reply,
        args=(incoming, from_number),
        daemon=True,
    ).start()

    return str(twiml)

# ---------- tarea asíncrona ---------------------------
def wait_and_reply(user_msg: str, to_number: str):
    try:
        # 1) crear hilo + run
        thread = openai_client.beta.threads.create()
        openai_client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_msg,
        )
        run = openai_client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID,
        )

        # 2) esperar hasta 60 s
        for _ in range(60):
            run = openai_client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id,
            )
            if run.status == "completed":
                break
            if run.status in ("failed", "cancelled", "expired"):
                send_msg("😕 Hubo un problema, inténtalo de nuevo.", to_number)
                return
            time.sleep(1)

        # 3) extraer respuesta
        msgs = openai_client.beta.threads.messages.list(thread_id=thread.id)
        answer = next(
            (m.content[0].text.value for m in msgs.data if m.role == "assistant"),
            "Lo siento, no pude responder.",
        )
        send_msg(answer, to_number)

    except Exception as e:
        logger.error("Error en wait_and_reply: %s", e, exc_info=True)
        send_msg("⚠️ Error interno. Vuelve a intentarlo más tarde.", to_number)

# ---------- envío (troceo automático) -----------------
def send_msg(body: str, to: str):
    text = body.strip()
    parts: list[str] = []

    while len(text) > MAX_LEN:
        cut = text.rfind("\n", 0, MAX_LEN)
        if cut == -1:
            cut = MAX_LEN
        parts.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    parts.append(text)

    for segment in parts:
        twilio_rest.messages.create(
            from_=TWILIO_FROM,
            to=to,
            body=segment,
        )
        time.sleep(0.3)       # pequeña pausa opcional

# ── ejecución local -----------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
