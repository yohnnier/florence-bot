from flask import Flask, request
import openai
import os
from twilio.twiml.messaging_response import MessagingResponse
import time

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

# Ruta raíz para probar que la app está funcionando
@app.route("/", methods=["GET"])
def home():
    return "Florence bot está en línea y operativo. 🚀"

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get('Body', '').strip()
    assistant_id = os.getenv("ASSISTANT_ID")

    thread = openai.beta.threads.create()
    
    openai.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=incoming_msg
    )

    run = openai.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant_id
    )

    # Esperar a que finalice
    for _ in range(15):
        run_check = openai.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run_check.status == "completed":
            break
        time.sleep(1)

    messages = openai.beta.threads.messages.list(thread_id=thread.id)
    reply = "No se pudo generar respuesta."

    for msg in messages.data:
        if msg.role == "assistant":
            reply = msg.content[0].text.value
            break

    twilio_resp = MessagingResponse()
    twilio_resp.message(reply)
    return str(twilio_resp)
