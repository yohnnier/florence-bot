from flask import Flask, request, abort
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import os, time, logging

app = Flask(__name__)

# ── OpenAI client ──────────────────────────────────────────────
openai_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    default_headers={"OpenAI-Beta": "assistants=v2"}
)
ASSISTANT_ID = os.getenv("ASSISTANT_ID")

# ── rutas ──────────────────────────────────────────────────────
@app.get("/")
def home():
    return "Florence bot está en línea 🚀"

@app.post("/webhook")
def webhook():
    """Recibe el mensaje de WhatsApp (Twilio) y responde."""
    incoming = request.values.get("Body", "").strip()
    if not incoming:
        abort(400, "No Body")

    # 1. Creamos un hilo
    thread = openai_client.beta.threads.create()

    # 2. Añadimos mensaje del usuario
    openai_client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=incoming,
    )

    # 3. Lanzamos la ejecución
    run = openai_client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=ASSISTANT_ID,
    )

    # 4. Esperamos máx 30 s a que termine
    for _ in range(30):
        run = openai_client.beta.threads.runs.retrieve(
            thread_id=thread.id, run_id=run.id
        )
        if run.status == "completed":
            break
        time.sleep(1)
    else:
        answer = "🤖 Tardo demasiado; inténtalo de nuevo en un minuto."
        twiml = MessagingResponse(); twiml.message(answer); return str(twiml)

    # 5. Leemos la respuesta del asistente
    msgs = openai_client.beta.threads.messages.list(thread_id=thread.id)
    answer = next(
        (m.content[0].text.value for m in msgs.data if m.role == "assistant"),
        "Lo siento, no pude generar respuesta."
    )

    # 6. Respondemos a Twilio
    twiml = MessagingResponse()
    twiml.message(answer)
    return str(twiml)

# ── logs más limpios en Render ─────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run()
