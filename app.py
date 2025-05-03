# app.py
from flask import Flask, request, abort
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import os, time, logging, sys

# ── Logging básico ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("florence‑bot")

# ── Flask ──────────────────────────────────────────────────────
app = Flask(__name__)

# ── Cliente OpenAI (SDK v1.23.2) ───────────────────────────────
try:
    openai_client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        # Usamos Assistants v2
        default_headers={"OpenAI-Beta": "assistants=v2"},
    )
    ASSISTANT_ID = os.getenv("ASSISTANT_ID")
    if not ASSISTANT_ID:
        raise RuntimeError("La variable ASSISTANT_ID no está definida")
    logger.info("✅ Cliente OpenAI inicializado")
except Exception as e:
    logger.error(f"❌ Error al inicializar OpenAI: {e}", exc_info=True)
    openai_client = None

# ── Rutas ──────────────────────────────────────────────────────
@app.get("/")
def home():
    return "Florence bot está en línea y operativo. 🚀"


@app.post("/webhook")
def webhook():
    """Endpoint que Twilio llama con cada mensaje entrante de WhatsApp."""
    # Si el cliente no existe devolvemos un mensaje genérico
    if not openai_client:
        resp = MessagingResponse()
        resp.message("Lo siento, el bot no está disponible.")
        return str(resp)

    incoming = request.values.get("Body", "").strip()
    from_number = request.values.get("From", "unknown")
    logger.info(f"Mensaje de {from_number}: {incoming!r}")

    if not incoming:
        abort(400, "Body vacío")

    try:
        # 1. Crear hilo
        thread = openai_client.beta.threads.create()
        # 2. Añadir mensaje del usuario
        openai_client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=incoming,
        )
        # 3. Ejecutar el assistant
        run = openai_client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID,
        )

        # 4. Esperar (máx 30 s)
        for _ in range(30):
            run = openai_client.beta.threads.runs.retrieve(
                thread_id=thread.id, run_id=run.id
            )
            if run.status == "completed":
                break
            if run.status in {"failed", "cancelled", "expired"}:
                raise RuntimeError(f"Ejecución terminada con estado {run.status}")
            time.sleep(1)
        else:
            raise TimeoutError("La generación tomó >30 s")

        # 5. Obtener la respuesta del assistant
        msgs = openai_client.beta.threads.messages.list(thread_id=thread.id)
        answer = next(
            (m.content[0].text.value for m in msgs.data if m.role == "assistant"),
            "Lo siento, no pude generar respuesta.",
        )

    except Exception as e:
        logger.error(f"Error en webhook: {e}", exc_info=True)
        answer = "🤖 Ocurrió un error interno. Inténtalo de nuevo en unos minutos."

    # 6. Responder a Twilio
    resp = MessagingResponse()
    resp.message(answer)
    return str(resp)


# ── Main local (Render usa gunicorn) ───────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
