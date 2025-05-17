import os
import json
import pickle
import numpy as np
import requests
from flask import Flask, request
from openai import OpenAI
from dotenv import load_dotenv
import faiss

# Carrega variables d'entorn
load_dotenv()
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "botfmb2025")

# Carrega els arxius d'embeddings i chunks
with open("index.pkl", "rb") as f:
    index = pickle.load(f)
with open("chunks.pkl", "rb") as f:
    chunks = pickle.load(f)

# Inicia Flask
app = Flask(__name__)

@app.route("/webhook", methods=["GET"])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if token == VERIFY_TOKEN:
        return challenge
    return "Verificació fallida", 403

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
                        phone_number_id = value["metadata"]["phone_number_id"]
                        sender = message["from"]
                        text = message.get("text", {}).get("body", "")

                        # Genera embedding de la pregunta
                        embedding = client.embeddings.create(
                            model="text-embedding-3-small",
                            input=[text]
                        ).data[0].embedding

                        # Busca context rellevant
                        D, I = index.search(np.array([embedding], dtype="float32"), k=5)
                        context = "\n\n".join([chunks[i] for i in I[0] if i < len(chunks)])

                        # Genera la resposta
                        resposta = client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[
                                {
                                    "role": "system",
                                    "content": f"Respon només amb la informació següent. Si no tens prou dades, digues-ho:\n\n{context}"
                                },
                                {
                                    "role": "user",
                                    "content": text
                                }
                            ]
                        ).choices[0].message.content

                        enviar_missatge_whatsapp(sender, resposta, phone_number_id)
    return "OK", 200

def enviar_missatge_whatsapp(destinatari, missatge, phone_number_id):
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
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
    response = requests.post(url, headers=headers, json=data)
    print("Missatge enviat:", response.status_code, response.text)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
