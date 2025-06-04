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

assert hasattr(index, "search"), "L'objecte FAISS no Ã©s vÃ lid."

user_sessions = {}
PERMISOS_LISTA = [
    "Matrimoni", "Canvi de domicili", "Naixement i cura de menor",
    "Visites mÃ¨diques", "ExÃ mens oficials", "DefunciÃ³ de familiar",
    "Assumptes propis", "Deures pÃºblics", "Judici per empresa",
    "Cura fills menors", "LactÃ ncia acumulada", "ReducciÃ³ de jornada",
    "ExÃ mens prenatals", "Sense sou", "ViolÃ¨ncia de gÃ¨nere",
    "AssistÃ¨ncia mÃ¨dica familiars", "AdopciÃ³ / acolliment", "JubilaciÃ³ parcial"
]

def detectar_idioma(text):
    esp = ["permiso", "consulta", "gracias", "usted", "quiero", "otra"]
    return "es" if any(p in text.lower() for p in esp) else "ca"

def missatge_benvinguda(lang):
    if lang == "es":
        return (
            "Bienvenido/a al asistente virtual de CCOO Metro de Barcelona.

"
            "Estoy aquÃ­ para ayudarte a resolver tus dudas.
"
            "Selecciona una de las siguientes opciones:

"
            "1 - Permisos laborales
"
            "2 - Otras consultas

"
            "Escribe el nÃºmero o el nombre de la opciÃ³n que quieres consultar."
        )
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

def text_nova_consulta(lang):
    return "Â¿Quieres realizar otra consulta? (sÃ­ / no)" if lang == "es" else "Vols fer una nova consulta? (sÃ­ / no)"

def text_descarregar_pdf(lang):
    return "Â¿Quieres descargar la tabla oficial de permisos? (sÃ­ / no)" if lang == "es" else "Vols descarregar la taula oficial de permisos? (sÃ­ / no)"

def text_final(lang):
    return (
        "Gracias por utilizar el asistente virtual de CCOO.
Si mÃ¡s adelante quieres hacer otra consulta, escribe la palabra CCOO."
        if lang == "es" else
        "GrÃ cies per utilitzar lâ€™assistent virtual de CCOO.
Si mÃ©s endavant vols tornar a fer una consulta, escriu la paraula CCOO."
    )

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
    try:
        embedding = client.embeddings.create(
            input=pregunta,
            model="text-embedding-3-small"
        ).data[0].embedding
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
    except Exception as e:
        print("Error generant la resposta:", str(e))
        return "Ho sento, ha fallat la generaciÃ³ de la resposta."

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
    try:
        entry = dades.get("entry", [])[0]
        change = entry.get("changes", [])[0]
        value = change.get("value", {})
        if "messages" not in value:
            return "OK", 200
        message = value["messages"][0]
        sender = message["from"]
        text = message["text"]["body"].strip()
        text_lower = text.lower()
    except Exception as e:
        print(f"Error llegint el missatge: {e}")
        return "OK", 200

    lang = detectar_idioma(text_lower)
    now = datetime.utcnow()
    session = user_sessions.get(sender, {
        "active": True,
        "file_sent": False,
        "state": "inici",
        "last_active": now,
        "lang": lang
    })

    session["lang"] = lang
    if (now - session["last_active"]).total_seconds() > 600:
        session = {"active": True, "file_sent": False, "state": "inici", "last_active": now, "lang": lang}
        enviar_missatge(sender, missatge_benvinguda(lang))

    session["last_active"] = now

    if not session["active"]:
        if text_lower == "ccoo":
            session = {"active": True, "file_sent": False, "state": "inici", "last_active": now, "lang": lang}
            enviar_missatge(sender, missatge_benvinguda(lang))
        user_sessions[sender] = session
        return "OK", 200

    if session["state"] == "inici":
        enviar_missatge(sender, missatge_benvinguda(lang))
        session["state"] = "menu"

    elif session["state"] == "menu":
        if text_lower in ["1", "permisos", "permÃ­s", "permiso"]:
            llistat = "\n".join([f"{i+1} - {nom}" for i, nom in enumerate(PERMISOS_LISTA)])
            enviar_missatge(sender, f"Consulta de permisos laborals.\nEscriu el nÃºmero o el nom del permÃ­s que vols consultar:\n\n{llistat}")
            session["state"] = "esperant_permÃ­s"
        elif text_lower in ["2", "altres", "otras", "otros"]:
            msg = (
                "Para otras consultas, puedes escribir a: ccoometro@tmb.cat"
                if lang == "es"
                else "Per altres consultes, pots escriure a: ccoometro@tmb.cat"
            )
            enviar_missatge(sender, f"{msg}\n\n{text_nova_consulta(lang)}")
            session["state"] = "post_resposta"

    elif session["state"] == "esperant_permÃ­s":
        try:
            idx = int(text) - 1
            if 0 <= idx < len(PERMISOS_LISTA):
                consulta = PERMISOS_LISTA[idx]
            else:
                consulta = text
        except:
            consulta = text
        try:
            resposta = generar_resposta(consulta)
            enviar_missatge(sender, resposta)
        except Exception as e:
            enviar_missatge(sender, f"Error generant la resposta: {str(e)}")

        if not session["file_sent"]:
            enviar_missatge(sender, text_descarregar_pdf(lang))
            session["state"] = "esperant_pdf"
        else:
            enviar_missatge(sender, text_nova_consulta(lang))
            session["state"] = "post_resposta"

    elif session["state"] == "esperant_pdf":
        if text_lower == "sÃ­" or text_lower == "si":
            enviar_document(sender)
            session["file_sent"] = True
        enviar_missatge(sender, text_nova_consulta(lang))
        session["state"] = "post_resposta"

    elif session["state"] == "post_resposta":
        if text_lower == "sÃ­" or text_lower == "si":
            enviar_missatge(sender, missatge_benvinguda(lang))
            session["state"] = "menu"
        elif text_lower == "no":
            enviar_missatge(sender, text_final(lang))
            session["active"] = False

    user_sessions[sender] = session
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
