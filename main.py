# -*- coding: utf-8 -*-
import os
from flask import Flask, request
import openai
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

openai.api_key = os.environ.get("OPENAI_API_KEY")
user_states = {}

WELCOME_MESSAGE = {
    "ca": (
        "Benvingut/da a l’assistent virtual de CCOO Metro de Barcelona.\n\n"
        "Soc aquí per ajudar-te a resoldre dubtes.\n"
        "Selecciona una de les següents opcions:\n\n"
        "1 - Permisos laborals\n"
        "2 - Altres consultes\n\n"
        "Escriu a continuació el número o el nom de l’opció que vols consultar."
    ),
    "es": (
        "Bienvenido/a al asistente virtual de CCOO Metro de Barcelona.\n\n"
        "Estoy aquí para ayudarte a resolver dudas.\n"
        "Selecciona una de las siguientes opciones:\n\n"
        "1 - Permisos laborales\n"
        "2 - Otras consultas\n\n"
        "Escribe a continuación el número o el nombre de la opción que quieres consultar."
    )
}

PERMISSIONS_LIST = {
    "ca": (
        "Aquí tens la llista de permisos disponibles:\n"
        "1 - Matrimoni\n"
        "2 - Naixement de fill/a\n"
        "3 - Defunció de familiar\n"
        "... (falten afegir tots)\n"
        "Escriu el número o el nom del permís que vols consultar."
    ),
    "es": (
        "Aquí tienes la lista de permisos disponibles:\n"
        "1 - Matrimonio\n"
        "2 - Nacimiento de hijo/a\n"
        "3 - Fallecimiento de familiar\n"
        "... (faltan por añadir todos)\n"
        "Escribe el número o el nombre del permiso que quieres consultar."
    )
}

PDF_MEDIA_ID = "637788649308962"

def detect_language(text):
    if any(word in text.lower() for word in ["bon dia", "permissos", "opció", "consulta"]):
        return "ca"
    return "es"

def reset_user_state(user_id):
    user_states[user_id] = {
        "active": True,
        "last_interaction": datetime.utcnow(),
        "language": "ca",
        "stage": "menu",
        "pdf_sent": False
    }

def check_inactivity(user_id):
    now = datetime.utcnow()
    if user_id in user_states:
        last_time = user_states[user_id].get("last_interaction")
        if last_time and now - last_time > timedelta(minutes=10):
            reset_user_state(user_id)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    message = data["messages"][0]
    user_text = message.get("text", {}).get("body", "").strip()
    user_id = message["from"]

    check_inactivity(user_id)
    state = user_states.get(user_id)

    if not state or user_text.upper() == "CCOO":
        reset_user_state(user_id)
        lang = detect_language(user_text)
        user_states[user_id]["language"] = lang
        return send_whatsapp_message(user_id, WELCOME_MESSAGE[lang])

    user_states[user_id]["last_interaction"] = datetime.utcnow()
    lang = user_states[user_id]["language"]

    if not user_states[user_id]["active"]:
        return "OK", 200

    if user_text.lower() in ["1", "permisos", "permiso", "permís"]:
        user_states[user_id]["stage"] = "permissions"
        return send_whatsapp_message(user_id, PERMISSIONS_LIST[lang])

    if user_states[user_id]["stage"] == "permissions":
        text_response = f"Aquesta és la informació literal del permís: \"{user_text}\"."
        send_whatsapp_message(user_id, text_response)

        if not user_states[user_id]["pdf_sent"]:
            user_states[user_id]["stage"] = "ask_pdf"
            return send_whatsapp_message(user_id, "Vols descarregar la taula oficial de permisos? (sí / no)")
        else:
            user_states[user_id]["stage"] = "ask_continue"
            return send_whatsapp_message(user_id, "Vols fer una nova consulta? (sí / no)")

    if user_states[user_id]["stage"] == "ask_pdf":
        if user_text.lower() == "sí":
            user_states[user_id]["pdf_sent"] = True
            send_document(user_id, PDF_MEDIA_ID)
        user_states[user_id]["stage"] = "ask_continue"
        return send_whatsapp_message(user_id, "Vols fer una nova consulta? (sí / no)")

    if user_states[user_id]["stage"] == "ask_continue":
        if user_text.lower() == "sí":
            user_states[user_id]["stage"] = "menu"
            return send_whatsapp_message(user_id, WELCOME_MESSAGE[lang])
        elif user_text.lower() == "no":
            user_states[user_id]["active"] = False
            return send_whatsapp_message(user_id, "Gràcies per utilitzar l’assistent. Escriu \"CCOO\" per tornar a activar-lo.")

    if user_text.lower() in ["2", "altres", "otras"]:
        user_states[user_id]["stage"] = "menu"
        return send_whatsapp_message(user_id, "Pots escriure la teva consulta a ccoometro@tmb.cat. Vols fer una altra consulta? (sí / no)")

    return "OK", 200

def send_whatsapp_message(to, text):
    url = "https://graph.facebook.com/v18.0/<580162021858021>/messages"
    headers = {
        "Authorization": f"Bearer {os.environ.get('WHATSAPP_TOKEN')}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    requests.post(url, headers=headers, json=payload)
    return "OK", 200

def send_document(to, media_id):
    url = "https://graph.facebook.com/v18.0/<PHONE_NUMBER_ID>/messages"
    headers = {
        "Authorization": f"Bearer {os.environ.get('WHATSAPP_TOKEN')}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "document",
        "document": {
            "id": media_id,
            "caption": "Quadre oficial de permisos laborals FMB"
        }
    }
    requests.post(url, headers=headers, json=payload)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
