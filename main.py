import os
import requests
import pickle
import faiss
import numpy as np
from flask import Flask, request
from openai import OpenAI
from datetime import datetime

app = Flask(__name__)
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

with open("index.pkl", "rb") as f:
    index = pickle.load(f)
with open("chunks.pkl", "rb") as f:
    chunk_texts = pickle.load(f)

user_sessions = {}
PERMISOS_LISTA = [
    "Matrimoni", "Canvi de domicili", "Naixement i cura de menor",
    "Visites mÃ¨diques", "ExÃ mens oficials", "DefunciÃ³ de familiar",
    "Assumptes propis", "Deures pÃºblics", "Judici per empresa",
    "Cura fills menors", "LactÃ ncia acumulada", "ReducciÃ³ de jornada",
    "ExÃ mens prenatals", "Sense sou", "ViolÃ¨ncia de gÃ¨nere",
    "AssistÃ¨ncia mÃ¨dica familiars", "AdopciÃ³ / acolliment", "JubilaciÃ³ parcial"
]

def enviar_missatge(destinatari, missatge):
    url = f"https://graph.facebook.com/v18.0/{os.environ['PHONE_NUMBER_ID']}/messages"
    headers = {
        "Authorization": f"Bearer {os.environ['WHATSAPP_TOKEN']}",
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
        "Authorization": f"Bearer {os.environ['WHATSAPP_TOKEN']}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": destinatari,
        "type": "document",
        "document": {
            "id": "1011069024514667",
            "filename": "Quadre_permisos_FMB.pdf"
        }
    }
    requests.post(url, headers=headers, json=data)

def generar_resposta(pregunta):
    embedding = client.embeddings.create(input=pregunta, model="text-embedding-3-small").data[0].embedding
    D, I = index.search(np.array([embedding]).astype("float32"), 3)
    context = "\n---\n".join([chunk_texts[i] for i in I[0]])
    resposta = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Respon segons el context proporcionat. Si no tens prou informaciÃ³, digues-ho."},
            {"role": "user", "content": f"Context:\n{context}\n\nPregunta: {pregunta}"}
        ]
    )
    return resposta.choices[0].message.content

@app.route("/", methods=["GET"])
def index():
    return "Bot viu!", 200

@app.route("/webhook", methods=["GET"])
def verificar_webhook():
    if request.args.get("hub.verify_token") == "ccoo2025":
        return request.args.get("hub.challenge")
    return "Token invÃ lid", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    dades = request.get_json()
    message = dades["entry"][0]["changes"][0]["value"]["messages"][0]
    sender = message["from"]
    text = message["text"]["body"].strip().lower()

    now = datetime.utcnow()
    session = user_sessions.get(sender, {
        "active": True,
        "file_sent": False,
        "state": "inici",
        "last_active": now
    })

    if (now - session["last_active"]).total_seconds() > 600:
        session = {"active": True, "file_sent": False, "state": "inici", "last_active": now}
        enviar_missatge(sender, missatge_benvinguda())

    session["last_active"] = now

    if not session["active"]:
        if text == "ccoo":
            session = {"active": True, "file_sent": False, "state": "inici", "last_active": now}
            enviar_missatge(sender, missatge_benvinguda())
        user_sessions[sender] = session
        return "OK", 200

    if session["state"] == "inici":
        enviar_missatge(sender, missatge_benvinguda())
        session["state"] = "menu"

    elif session["state"] == "menu":
        if text in ["1", "permisos"]:
            llistat = "\n".join([f"{i+1} - {nom}" for i, nom in enumerate(PERMISOS_LISTA)])
            enviar_missatge(sender, f"Consulta de permisos laborals.\nEscriu el nÃºmero o el nom del permÃ­s que vols consultar:\n\n{llistat}")
            session["state"] = "esperant_permÃ­s"
        elif text in ["2", "altres"]:
            enviar_missatge(sender, "Per altres consultes, pots escriure a: ccoometro@tmb.cat\n\nVols fer una nova consulta? (sÃ­ / no)")
            session["state"] = "post_resposta"

    elif session["state"] == "esperant_permÃ­s":
        try:
            idx = int(text) - 1
            consulta = PERMISOS_LISTA[idx] if 0 <= idx < len(PERMISOS_LISTA) else text
        except:
            consulta = text
        resposta = generar_resposta(consulta)
        enviar_missatge(sender, resposta)
        if not session["file_sent"]:
            enviar_missatge(sender, "Vols descarregar la taula oficial de permisos? (sÃ­ / no)")
            session["state"] = "esperant_pdf"
        else:
            enviar_missatge(sender, "Vols fer una nova consulta? (sÃ­ / no)")
            session["state"] = "post_resposta"

    elif session["state"] == "esperant_pdf":
        if text == "sÃ­":
            enviar_document(sender)
            session["file_sent"] = True
        enviar_missatge(sender, "Vols fer una nova consulta? (sÃ­ / no)")
        session["state"] = "post_resposta"

    elif session["state"] == "post_resposta":
        if text == "sÃ­":
            enviar_missatge(sender, missatge_benvinguda())
            session["state"] = "menu"
        elif text == "no":
            enviar_missatge(sender, "GrÃ cies per utilitzar lâ€™assistent virtual de CCOO.
Si mÃ©s endavant vols tornar a fer una consulta, escriu la paraula CCOO.")
            session["active"] = False

    user_sessions[sender] = session
    return "OK", 200

def missatge_benvinguda():
    return (
        "Benvingut/da a lâ€™assistent virtual de CCOO Metro de Barcelona.

"
        "Soc aquÃ­ per ajudar-te a resoldre dubtes.
"
        "Selecciona una de les segÃ¼ents opcions:

"
        "1 - Permisos laborals
"
        "2 - Altres consultes

"
        "Escriu a continuaciÃ³ el nÃºmero o el nom de lâ€™opciÃ³ que vols consultar."
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
