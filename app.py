# app.py
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import os, time, logging

# ------------------------------------------------------------------
# CONFIGURACIÓN BÁSICA
# ------------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID   = os.getenv("ASSISTANT_ID")   # ← id del Assistant que creaste

#  🔑  Cliente OpenAI con cabecera obligatoria `assistants=v2`
client = OpenAI(
    api_key=OPENAI_API_KEY,
    default_headers={"OpenAI-Beta": "assistants=v2"},
)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


# ------------------------------------------------------------------
# RUTA DE SALUD
# ------------------------------------------------------------------
@app.route("/", methods=["GET"])
def healthcheck():
    return "Florence bot está en línea y operativo. 🚀"


# ------------------------------------------------------------------
# WEBHOOK PARA TWILIO / WHATSAPP
# ------------------------------------------------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip()

    resp_twilio = MessagingResponse()

    if not incoming_msg:
        resp_twilio.message("No recibí ningún texto. ¿Podrías repetirlo?")
        return str(resp_twilio)

    try:
        # 1. Crea un hilo
        thread = client.beta.threads.create()

        # 2. Añade el mensaje del usuario
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=incoming_msg,
        )

        # 3. Lanza la ejecución con tu Assistant
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID,
        )

        # 4. Espera hasta 15 s a que finalice
        for _ in range(15):
            run_check = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id,
            )
            if run_check.status == "completed":
                break
            time.sleep(1)

        # 5. Obtiene la primera respuesta del Assistant
        reply = "Lo siento, no pude generar respuesta a tiempo."
        msgs = client.beta.threads.messages.list(thread_id=thread.id)
        for m in msgs.data:
            if m.role == "assistant":
                reply = m.content[0].text.value
                break

    except Exception as e:
        logging.exception("Error procesando mensaje")
        reply = "❌ Ocurrió un error interno. Inténtalo de nuevo en unos minutos."

    # 6. Devuelve la respuesta a WhatsApp
    resp_twilio.message(reply)
    return str(resp_twilio)


# ------------------------------------------------------------------
# EJECUCIÓN LOCAL (opcional)
# ------------------------------------------------------------------
if __name__ == "__main__":
    # Solo para pruebas locales:  flask run  ó  python app.py
    app.run(debug=True, port=5000)
