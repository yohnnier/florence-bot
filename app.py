from flask import Flask, request
import openai
import os
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get('Body', '').strip()

    assistant_id = os.getenv("ASSISTANT_ID")
    thread = openai.beta.threads.create()
    response = openai.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=incoming_msg
    )
    run = openai.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant_id
    )

    # Esperamos hasta que finalice la ejecución
    while True:
        run_check = openai.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run_check.status == "completed":
            break

    messages = openai.beta.threads.messages.list(thread_id=thread.id)
    reply = messages.data[0].content[0].text.value if messages.data else "No se pudo generar respuesta."

    twilio_resp = MessagingResponse()
    twilio_resp.message(reply)
    return str(twilio_resp)
