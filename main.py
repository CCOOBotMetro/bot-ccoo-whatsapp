import requests
import os
import json
from flask import Flask, request
from openai import OpenAI
from docx import Document
import pickle
import numpy as np
import faiss

# Carreguem els arxius de context
with open("chunks.pkl", "rb") as f:
    chunks = pickle.load(f)

with open("index.pkl", "rb") as f:
    index = pickle.load(f)

# Inicialitzem OpenAI i Flask
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "botfmb2025")
PDF_MEDIA_ID = os.environ.get("PDF_MEDIA_ID", "637788649308962")
WA_TOKEN = os.environ.get("WHATSAPP_TOKEN")

user_states = {}
salutacions = ["hola", "hola!", "bon dia", "bon dia!", "bona tarda", "bona tarda!", "bona nit", "bona nit!"]

info_intro = (
    "Gràcies per contactar amb CCOO de Metro de Barcelona, soc el BOT Virtual i soc aquí per ajudar-te a resoldre els teus dubtes. "
    "A continuació et detallaré un índex de la informació que disposo:\n"
)
index_text = "1 – Permisos\n2 – Altres"

# Funcions

def enviar_missatge(destinatari, missatge):
    url = f"https://graph.facebook.com/v18.0/{os.environ['PHONE_NUMBER_ID']}/messages"
    headers = {
        "Authorization": f"Bearer {WA_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": destinatari,
        "type": "text",
        "text": {"body": missatge}
    }
    requests.post(url, headers=headers, json=data)

def enviar_document(destinatari):
    url = f"https://graph.facebook.com/v18.0/{os.environ['PHONE_NUMBER_ID']}/messages"
    headers = {
        "Authorization": f"Bearer {WA_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": destinatari,
        "type": "document",
        "document": {
            "id": PDF_MEDIA_ID,
            "filename": "Quadre permisos FMB.pdf"
        }
    }
    requests.post(url, headers=headers, json=data)

# Rutes

@app.route("/webhook", methods=["GET"])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if token == VERIFY_TOKEN:
        return challenge
    return "Token invalid", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if data.get("object") == "whatsapp_business_account":
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                if messages:
                    for message in messages:
                        sender = message["from"]
                        text = message.get("text", {}).get("body", "").strip()

                        lower_text = text.lower()

                        if user_states.get(sender, {}).get("waiting_for_bot"):
                            enviar_missatge(sender, "Bot reactivat! Pots fer-me una nova consulta.")
                            user_states[sender] = {"step": 0, "doc_sent": False}
                            return "OK", 200

                        if lower_text == "bot":
                            user_states[sender] = {"waiting_for_bot": True}
                            return "OK", 200

                        state = user_states.get(sender, {"step": 0, "doc_sent": False})

                        if any(lower_text.startswith(s) for s in salutacions) and state["step"] == 0:
                            enviar_missatge(sender, info_intro + index_text)
                            user_states[sender] = {"step": 1, "doc_sent": False}

                        elif lower_text in ["1", "permisos"] and state["step"] == 1:
                            llista = "\n".join([f"{i+1}. Permís {i+1}" for i in range(len(chunks))])
                            enviar_missatge(sender, f"Disposo d'aquestes opcions:\n{llista}\nDigues el número del permís que vols consultar.")
                            user_states[sender]["step"] = 2

                        elif state["step"] == 2 and lower_text.isdigit():
                            num = int(lower_text)
                            if 1 <= num <= len(chunks):
                                resposta = chunks[num-1]
                                enviar_missatge(sender, resposta)
                                if not state["doc_sent"]:
                                    enviar_missatge(sender, "Vols descarregar la taula oficial de permisos? (Respon: sí / no)")
                                    user_states[sender]["step"] = 3
                                else:
                                    enviar_missatge(sender, "Vols fer una nova consulta? (sí / no)")
                                    user_states[sender]["step"] = 4

                        elif state["step"] == 3:
                            if lower_text in ["si", "sí"]:
                                enviar_document(sender)
                                user_states[sender]["doc_sent"] = True
                                enviar_missatge(sender, "Vols fer una nova consulta? (sí / no)")
                                user_states[sender]["step"] = 4
                            elif lower_text == "no":
                                enviar_missatge(sender, "Vols fer una nova consulta? (sí / no)")
                                user_states[sender]["step"] = 4

                        elif lower_text in ["2", "altres"] and state["step"] == 1:
                            enviar_missatge(sender, "Escriu el teu dubte i en breu ens posarem en contacte amb tu. També pots escriure a ccoometro@tmb.cat")
                            user_states[sender]["step"] = 5

                        elif state["step"] == 5:
                            enviar_missatge(sender, "Vols fer una nova consulta? (sí / no)")
                            user_states[sender]["step"] = 4

                        elif state["step"] == 4:
                            if lower_text in ["si", "sí"]:
                                enviar_missatge(sender, index_text)
                                user_states[sender]["step"] = 1
                            else:
                                enviar_missatge(sender, "Gràcies per contactar. Per tornar a activar el bot, escriu la paraula BOT.")
                                user_states[sender] = {"waiting_for_bot": True}

                        else:
                            enviar_missatge(sender, "No disposo d’aquesta informació concreta, però pròximament ens posarem en contacte per respondre el teu dubte. Necessites alguna cosa més?")
                            user_states[sender]["step"] = 4

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

