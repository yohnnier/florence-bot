# app.py  (añade al comienzo)
import threading
from twilio.rest import Client as TwilioRest

twilio_rest = TwilioRest(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)
TWILIO_FROM = "whatsapp:+13158123738"  # tu sender sandbox

# ---------- webhook ----------
@app.post("/webhook")
def webhook():
    incoming = request.values.get("Body", "").strip()
    from_number = request.values.get("From")

    # --- 1. contestación inmediata ---
    twiml = MessagingResponse()
    twiml.message("✔️ Recibido, dame unos segundos…")
    threading.Thread(
        target=wait_and_reply,
        args=(incoming, from_number)
    ).start()
    return str(twiml)

# ------- tarea en 2º plano ----------
def wait_and_reply(user_msg: str, to_number: str):
    # 1) crear hilo y run
    thread = openai_client.beta.threads.create()
    openai_client.beta.threads.messages.create(
        thread_id=thread.id, role="user", content=user_msg
    )
    run = openai_client.beta.threads.runs.create(
        thread_id=thread.id, assistant_id=ASSISTANT_ID
    )

    # 2) esperar a que termine
    while True:
        run = openai_client.beta.threads.runs.retrieve(
            thread_id=thread.id, run_id=run.id
        )
        if run.status == "completed":
            break
        if run.status in ["failed", "cancelled", "expired"]:
            send_msg("😕 Hubo un problema, inténtalo de nuevo.", to_number)
            return
        time.sleep(2)

    # 3) obtener respuesta del assistant
    msgs = openai_client.beta.threads.messages.list(thread_id=thread.id)
    answer = next((m.content[0].text.value for m in msgs.data
                   if m.role == "assistant"), "Lo siento, no pude responder.")
    send_msg(answer, to_number)

def send_msg(body, to):
    twilio_rest.messages.create(
        from_=TWILIO_FROM,
        to=to,
        body=body
    )
