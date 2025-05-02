from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from tinydb import TinyDB, Query                    # ⬅️ NEW
import openai
import os
import time

# ------------- configuración básica -------------
app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")
assistant_id = os.getenv("ASSISTANT_ID")

# base de datos local (archivo JSON de pocas KB)
db = TinyDB("threads.json")
Q  = Query()
# ------------------------------------------------


# ---------- RUTA RAÍZ ----------
@app.route("/", methods=["GET"])
def home():
    return "Florence bot está en línea y operativo. 🚀"
# --------------------------------


# ---------- WEBHOOK DE WHATSAPP ----------
@app.route("/webhook", methods=["POST"])
def webhook():
    # 1. mensaje entrante
    incoming_msg  = request.values.get("Body", "").strip()
    user_number   = request.values.get("From", "")  # ej. '+1415xxxx'
    if not incoming_msg:
        return "OK"

    # 2. buscar / crear thread para ese usuario
    row = db.get(Q.user == user_number)
    if row:
        thread_id = row["thread"]
    else:
        thread_id = openai.beta.threads.create().id
        db.insert({"user": user_number, "thread": thread_id})

    # 3. agregar mensaje del usuario
    openai.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=incoming_msg
    )

    # 4. iniciar ejecución del assistant
    run = openai.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id
    )

    # 5. esperar a que termine (máx 15 s)
    for _ in range(15):
        run_check = openai.beta.threads.runs.retrieve(
            thread_id=thread_id, run_id=run.id
        )
        if run_check.status == "completed":
            break
        time.sleep(1)

    # 6. obtener la última respuesta del assistant
    reply = "Lo siento, tardé demasiado en generar respuesta."
    try:
        msgs = openai.beta.threads.messages.list(thread_id=thread_id)
        for msg in msgs.data:
            if msg.role == "assistant":
                reply = msg.content[0].text.value
                break
    except Exception as e:
        reply = f"Error al obtener respuesta: {e}"

    # 7. enviar de vuelta a WhatsApp
    tw_resp = MessagingResponse()
    tw_resp.message(reply)
    return str(tw_resp)
# ----------------------------------------------


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)
