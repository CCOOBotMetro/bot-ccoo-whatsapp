import os
import requests
from flask import Flask, request
from openai import OpenAI

# ---------- Configuració bàsica ----------

app = Flask(__name__)

# Variables d'entorn (les definiràs a Render)
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# Prompt del bot (versió simple, només permisos)
SYSTEM_PROMPT = """
Ets el bot sindical de CCOO Metro de Barcelona especialitzat en PERMISOS LABORALS.

- Respon només sobre permisos, conciliació i temes relacionats (visites mèdiques, defuncions, matrimoni, canvis de domicili, etc.).
- Si la consulta NO és de permisos, digues de manera educada que només pots informar sobre permisos.
- Respon SEMPRE en el mateix idioma que la persona usuària (català o castellà).
- Explica-ho clar i de manera entenedora, com si ho expliquessis a un company o companya de feina.
- No t'inventis lleis concretes; si no estàs segur, recomana consultar-ho amb CCOO Metro directament.
"""

# ---------- Funcions auxiliars ----------

def send_whatsapp_text(to_number: str, message: str):
    """
    Envia un missatge de text a través de la WhatsApp Cloud API.
    """
    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {
            "body": message
        }
    }
    response = requests.post(url, headers=headers, json=data)
    if not response.ok:
        print("Error enviant missatge a WhatsApp:", response.text)


def ask_openai_about_permisos(user_text: str) -> str:
    """
    Envia la consulta a OpenAI perquè respongui com a bot de permisos.
    De moment no fem servir documents, només el SYSTEM_PROMPT.
    """
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
            temperature=0.2,
        )
        answer = completion.choices[0].message.content.strip()
        return answer
    except Exception as e:
        print("Error amb OpenAI:", e)
        # Missatge de fallback
        return (
            "Ara mateix tinc un problema tècnic per respondre. "
            "Pots contactar directament amb CCOO Metro o tornar-ho a provar d'aquí una estona."
        )

# ---------- Rutes del servidor ----------

@app.route("/", methods=["GET"])
def home():
    return "Bot CCOO Permisos està funcionant.", 200


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        # Verificació del webhook (Meta → servidor)
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            print("Webhook verificat correctament!")
            return challenge, 200
        else:
            print("Error de verificació del webhook.")
            return "Error de verificació", 403

    if request.method == "POST":
        data = request.get_json()
        # DEBUG opcional
        # print("Webhook rebut:", data)

        # Comprovar que hi ha notificació de missatge
        if data.get("object") == "whatsapp_business_account":
            for entry in data.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    messages = value.get("messages", [])

                    for message in messages:
                        process_incoming_message(message, value)

        return "OK", 200


def process_incoming_message(message: dict, value: dict):
    """
    Gestiona un missatge entrant de WhatsApp.
    De moment: només text, i respon amb info de permisos.
    """
    from_number = message["from"]  # número de la persona
    msg_type = message.get("type")

    # Només tractem missatges de text
    if msg_type == "text":
        user_text = message["text"]["body"].strip()
    else:
        # Si no és text, enviem un missatge educat
        send_whatsapp_text(
            from_number,
            "De moment només puc llegir missatges de text. "
            "Si us plau, escriu la teva consulta sobre permisos."
        )
        return

    # Aquí podríem detectar salutacions i enviar un missatge de benvinguda especial,
    # però de moment ho enviem directament a OpenAI.
    answer = ask_openai_about_permisos(user_text)

    send_whatsapp_text(from_number, answer)


# Per executar en local (per proves amb ngrok, per exemple)
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
