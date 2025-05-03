from flask import Flask, request, abort
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import os, time, logging, sys

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ── OpenAI client ──────────────────────────────────────────────
try:
    # Inicializar cliente usando solo api_key (sin proxies)
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    # Añadir headers para assistants v2 después de la inicialización
    openai_client.default_headers = {"OpenAI-Beta": "assistants=v2"}
    ASSISTANT_ID = os.getenv("ASSISTANT_ID")
    logger.info("Cliente OpenAI inicializado correctamente")
except Exception as e:
    logger.error(f"Error al inicializar el cliente OpenAI: {str(e)}")
    openai_client = None

# ── rutas ──────────────────────────────────────────────────────
@app.get("/")
def home():
    logger.info("Acceso a la ruta principal")
    return "Florence bot está en línea y operativo. 🚀"

@app.post("/webhook")
def webhook():
    """Recibe el mensaje de WhatsApp (Twilio) y responde."""
    try:
        # Verificar si el cliente OpenAI está disponible
        if not openai_client:
            logger.error("No se puede procesar la solicitud: cliente OpenAI no disponible")
            response = MessagingResponse()
            response.message("Lo siento, hay un problema de configuración. Por favor contacta al administrador.")
            return str(response)

        # Obtener el mensaje entrante
        incoming = request.values.get("Body", "").strip()
        from_number = request.values.get("From", "unknown")
        
        logger.info(f"Mensaje recibido de {from_number}: {incoming[:20]}...")
        
        if not incoming:
            logger.warning("Mensaje vacío recibido")
            abort(400, "No Body")

        # 1. Creamos un hilo
        thread = openai_client.beta.threads.create()
        logger.info(f"Hilo creado: {thread.id}")

        # 2. Añadimos mensaje del usuario
        openai_client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=incoming,
        )
        logger.info("Mensaje añadido al hilo")

        # 3. Lanzamos la ejecución
        run = openai_client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID,
        )
        logger.info(f"Ejecución iniciada: {run.id}")

        # 4. Esperamos máx 30 s a que termine
        for i in range(30):
            run = openai_client.beta.threads.runs.retrieve(
                thread_id=thread.id, run_id=run.id
            )
            if run.status == "completed":
                logger.info(f"Ejecución completada después de {i+1} segundos")
                break
            elif run.status in ["failed", "cancelled", "expired"]:
                logger.error(f"Ejecución terminada con estado: {run.status}")
                answer = f"🤖 Ocurrió un error: {run.status}. Por favor intenta nuevamente."
                twiml = MessagingResponse()
                twiml.message(answer)
                return str(twiml)
            time.sleep(1)
        else:
            logger.warning("Tiempo de espera agotado después de 30 segundos")
            answer = "🤖 Tardo demasiado; inténtalo de nuevo en un minuto."
            twiml = MessagingResponse()
            twiml.message(answer)
            return str(twiml)

        # 5. Leemos la respuesta del asistente
        msgs = openai_client.beta.threads.messages.list(thread_id=thread.id)
        answer = next(
            (m.content[0].text.value for m in msgs.data if m.role == "assistant"),
            "Lo siento, no pude generar respuesta."
        )
        logger.info(f"Respuesta generada: {answer[:50]}...")

        # 6. Respondemos a Twilio
        twiml = MessagingResponse()
        twiml.message(answer)
        return str(twiml)
        
    except Exception as e:
        logger.error(f"Error en webhook: {str(e)}", exc_info=True)
        twiml = MessagingResponse()
        twiml.message("Lo siento, ocurrió un error al procesar tu mensaje. Inténtalo nuevamente más tarde.")
        return str(twiml)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
