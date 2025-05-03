# … (imports y config previos idénticos) …

MAX_CHARS = 1500          # margen seguro < 1600 sandbox

# ---------- webhook ---------- #
@app.post("/webhook")
def webhook():
    incoming = request.values.get("Body", "").strip()
    from_number = request.values.get("From")
    if not incoming:
        abort(400, "mensaje vacío")

    ack = MessagingResponse()
    ack.message("✔️ Recibido, dame unos segundos…")

    threading.Thread(
        target=wait_and_reply,
        args=(incoming, from_number),
        daemon=True
    ).start()
    return str(ack)

# ------- tarea en 2º plano ---------- #
def wait_and_reply(user_msg: str, to_number: str):
    try:
        # 1) Assistant
        thread = openai_client.beta.threads.create()
        openai_client.beta.threads.messages.create(
            thread_id=thread.id, role="user", content=user_msg
        )
        run = openai_client.beta.threads.runs.create(
            thread_id=thread.id, assistant_id=ASSISTANT_ID
        )

        # 2) Poll
        for _ in range(90):                  # 90 s máx
            run = openai_client.beta.threads.runs.retrieve(
                thread_id=thread.id, run_id=run.id
            )
            if run.status == "completed":
                break
            if run.status in ("failed", "cancelled", "expired"):
                send_msg("😕 El asistente no pudo responder, inténtalo de nuevo.", to_number)
                return
            time.sleep(1)

        # 3) Obtener respuesta
        msgs = openai_client.beta.threads.messages.list(thread_id=thread.id)
        answer = next(
            (m.content[0].text.value for m in msgs.data if m.role == "assistant"),
            "Lo siento, no pude responder."
        )

        # 4) Enviar en trozos ≤ MAX_CHARS
        for chunk in split_chunks(answer, MAX_CHARS):
            send_msg(chunk, to_number)

    except Exception as e:
        logger.error("Error en wait_and_reply: %s", e, exc_info=True)
        send_msg("⚠️ Error interno. Vuelve a intentarlo más tarde.", to_number)

def split_chunks(text: str, size: int):
    """Genera trozos de longitud <= size sin cortar palabras."""
    while len(text) > size:
        cut = text.rfind(" ", 0, size)
        cut = cut if cut != -1 else size
        yield text[:cut]
        text = text[cut:].lstrip()
    yield text

def send_msg(body: str, to: str):
    try:
        twilio_rest.messages.create(from_=TWILIO_FROM, to=to, body=body)
    except Exception as e:
        logger.error("Twilio send error: %s", e, exc_info=True)
        raise                                             # se capturará arriba

# — main —
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
