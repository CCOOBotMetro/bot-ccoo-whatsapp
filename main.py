import os
import json
import pickle
import requests
from flask import Flask, request
from openai import OpenAI
import numpy as np
import faiss
# Inicialitza Flask
app = Flask(__name__)
# Carrega els arxius
with open("index.pkl", "rb") as f:
   index = pickle.load(f)
with open("chunks.pkl", "rb") as f:
   chunk_texts = pickle.load(f)
# Inicialitza OpenAI
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "botfmb2025")
WHATSAPP_TOKEN = os.environ["WHATSAPP_TOKEN"]
# Ruta per a la verificació del webhook
@app.route("/webhook", methods=["GET"])
def verify():
   if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.verify_token") == VERIFY_TOKEN:
       return request.args.get("hub.challenge")
   return "Error de verificació", 403
# Ruta per rebre missatges
@app.route("/webhook", methods=["POST"])
def webhook():
   data = request.get_json()
   if data.get("entry"):
       for entry in data["entry"]:
           for change in entry["changes"]:
               value = change["value"]
               if "messages" in value:
                   message = value["messages"][0]
                   text = message["text"]["body"]
                   sender_id = message["from"]
                   # Fer embedding i buscar resposta
                   embedding = client.embeddings.create(
                       input=text,
                       model="text-embedding-3-small"
                   ).data[0].embedding
                   D, I = index.search(np.array([embedding]).astype("float32"), 3)
                   context_str = "\n---\n".join([chunk_texts[i] for i in I[0]])
                   resposta = client.chat.completions.create(
                       model="gpt-3.5-turbo",
                       messages=[
                           {"role": "system", "content": "Respon segons el context proporcionat. Si no tens prou informació, digues-ho."},
                           {"role": "user", "content": f"Context:\n{context_str}\n\nPregunta: {text}"}
                       ]
                   )
                   resposta_final = resposta.choices[0].message.content
                   # Enviar la resposta per WhatsApp
                   url = "https://graph.facebook.com/v18.0/me/messages"
                   headers = {
                       "Authorization": f"Bearer {WHATSAPP_TOKEN}",
                       "Content-Type": "application/json"
                   }
                   payload = {
                       "messaging_product": "whatsapp",
                       "to": sender_id,
                       "type": "text",
                       "text": {"body": resposta_final}
                   }
                   requests.post(url, headers=headers, data=json.dumps(payload))
   return "ok", 200
if __name__ == "__main__":
   app.run(debug=True)
