import os
import requests
from flask import Flask, request
from openai import OpenAI
import faiss
import numpy as np
import pickle

app = Flask(__name__)

# Carrega l’índex i els textos
with open("index.pkl", "rb") as f:
    index = pickle.load(f)
with open("chunks.pkl", "rb") as f:
    chunk_texts = pickle.load(f)

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# Missatge de text simple
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
        "text": { "body": missatge }
    }
    requests.post(url, headers=headers, json=data)

# Botons interactius
def enviar_botons_interactius(destinatari):
    url = f"https://graph.facebook.com/v18.0/{os.environ['PHONE_NUMBER_ID']}/messages"
    headers = {
        "Authorization": f"Bearer {os.environ['WHATSAPP_TOKEN']}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": destinatari,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": "Gràcies per contactar amb CCOO de Metro de Barcelona. Soc el BOT virtual, escull una opció:"
            },
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": { "id": "opc1_permisos", "title": "Permisos" }
                    },
                    {
                        "type": "reply",
                        "reply": { "id": "opc2_altres", "title": "Altres" }
                    }
                ]
            }
        }
    }
    requests.post(url, headers=headers, json=data)

# Resposta amb embeddings
def generar_resposta(pregunta):
    embedding = client.embeddings.create(
        input=pregunta,
        model="text-embedding-3-small"
    ).data[0].embedding
    D, I = index.search(np.array([embedding]).astype("float32"), 3)
    context = "\n---\n".join([chunk_texts[i] for i in I[0]])
    resposta = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Respon segons el context proporcionat. Si no tens prou informació, digues-ho."},
            {"role": "user", "content": f"Context:\n{context}\n\nPregunta: {pregunta}"}
        ]
    )
    return resposta.choices[0].message.content

@app.route("/", methods=["GET"])
def index():
    return "Bot viu!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    dades = request.get_json()
    try:
        message = dades["entry"][0]["changes"][0]["value"]["messages"][0]
        sender = message["from"]

        # Si és un text normal
        if "text" in message:
            text = message["text"]["body"].strip()
            if text.lower() == "bot":
                enviar_botons_interactius(sender)
                return "OK", 200
            else:
                enviar_missatge(sender, "Per activar el bot escriu la paraula *BOT*.")
                return "OK", 200

        # Si ha premut un botó
        if "interactive" in message:
            inter = message["interactive"]
            if inter["type"] == "button_reply":
                resposta_id = inter["button_reply"]["id"]

                if resposta_id == "opc1_permisos":
                    enviar_missatge(sender, "Has seleccionat *Permisos*. Escriu el nom del permís o una consulta concreta.")
                    return "OK", 200

                elif resposta_id == "opc2_altres":
                    enviar_missatge(sender, "Has seleccionat *Altres*. Escriu la teva consulta i ens posarem en contacte.")
                    return "OK", 200

    except Exception as e:
        print("ERROR al webhook:", e)

    return "OK", 200

# PORT correctament exposat per Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
