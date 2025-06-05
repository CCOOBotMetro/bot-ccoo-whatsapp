import os
import pickle
import faiss
import numpy as np
from flask import Flask, request
from datetime import datetime
import requests
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

with open("index.pkl", "rb") as f:
    index = pickle.load(f)
with open("chunks.pkl", "rb") as f:
    chunk_texts = pickle.load(f)

assert hasattr(index, "search"), "L'índex FAISS no és vàlid."

PERMISOS_LISTA = [
    "Matrimoni", "Canvi de domicili", "Naixement i cura de menor",
    "Visites mèdiques", "Exàmens oficials", "Defunció de familiar",
    "Assumptes propis", "Deures públics", "Judici per empresa",
    "Cura fills menors", "Lactància acumulada", "Reducció de jornada",
    "Exàmens prenatals", "Sense sou", "Violència de gènere",
    "Assistència mèdica familiars", "Adopció / acolliment", "Jubilació parcial"
]

user_sessions = {}

def detectar_idioma(text):
    return "es" if any(p in text.lower() for p in ["permiso", "consulta", "gracias", "usted", "quiero", "otra"]) else "ca"

def missatge_benvinguda(lang):
    if lang == "es":
        return (
            "Bienvenido/a al asistente virtual de CCOO Metro de Barcelona.\n\n"
            "Estoy aquí para ayudarte a resolver tus dudas.\n"
            "Selecciona una de las siguientes opciones:\n\n"
            "1 - Permisos laborales\n"
            "2 - Otras consultas\n\n"
            "Escribe el número o el nombre de la opción que quieres consultar."
        )
    return (
        "Benvingut/da a l’assistent virtual de CCOO Metro de Barcelona.\n\n"
        "Soc aquí per ajudar-te a resoldre dubtes.\n"
        "Selecciona una de les següents opcions:\n\n"
        "1 - Permisos laborals\n"
        "2 - Altres consultes\n\n"
        "Escriu el número o el nom de l’opció que vols consultar."
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

def generar_resposta(pregunta):
    try:
        embedding = client.embeddings.create(input=pregunta, model="text-embedding-3-small").data[0].embedding
        D, I = index.search(np.array([embedding]).astype("float32"), 3)
        print("🔍 FAISS index:", I)

        context = "\n---\n".join([chunk_texts[i] for i in I[0]])
        print("📄 Context seleccionat:", context[:500])

        resposta = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Respon segons el context proporcionat. Si no tens prou informació, digues-ho."},
                {"role": "user", "content": f"Context:\n{context}\n\nPregunta: {pregunta}"}
            ]
        )
        return resposta.choices[0].message.content
    except Exception as e:
        print("❌ Error generant la resposta:", str(e))
        return "Ho sento, ha fallat la generació de la resposta."

@app.route("/", methods=["GET"])
def index():
    return "Bot viu!", 200

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
        print("❌ Error processant el missatge:", str(e))
        return "OK", 200

    lang = detectar_idioma(text_lower)
    try:
        resposta = generar_resposta(text)
        enviar_missatge(sender, resposta)
    except Exception as e:
        print("❌ Error general:", str(e))
        enviar_missatge(sender, "Ho sento, ha fallat la generació de la resposta.")
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
