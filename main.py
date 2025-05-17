from flask import Flask, request
import os
import json
import openai
import faiss
import numpy as np
import pickle
# Carrega la clau d’API d’OpenAI
openai.api_key = os.environ["OPENAI_API_KEY"]
# Carrega l’índex FAISS i els trossos de text
with open("index.pkl", "rb") as f:
   index = pickle.load(f)
with open("chunks.pkl", "rb") as f:
   chunk_texts = pickle.load(f)
# Crea l'aplicació Flask
app = Flask(__name__)
# Verificació del webhook de Meta
@app.route("/webhook", methods=["GET"])
def verify():
   verify_token = os.environ.get("VERIFY_TOKEN")
   mode = request.args.get("hub.mode")
   token = request.args.get("hub.verify_token")
   challenge = request.args.get("hub.challenge")
   if mode == "subscribe" and token == verify_token:
       return challenge, 200
   else:
       return "Unauthorized", 403
# Tractar missatges entrants
@app.route("/webhook", methods=["POST"])
def webhook():
   data = request.get_json()
   try:
       message = data["entry"][0]["changes"][0]["value"]["messages"][0]
       user_message = message["text"]["body"]
       phone_number_id = data["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"]
       sender_id = message["from"]
       # Crear embedding
       embedding = openai.Embedding.create(
           input=user_message,
           model="text-embedding-3-small"
       )["data"][0]["embedding"]
       # Buscar contextos més rellevants
       D, I = index.search(np.array([embedding]).astype("float32"), 3)
       context = "\n---\n".join([chunk_texts[i] for i in I[0]])
       # Generar resposta
       resposta = openai.ChatCompletion.create(
           model="gpt-3.5-turbo",
           messages=[
               {"role": "system", "content": "Respon segons el context proporcionat. Si no tens prou informació, digues-ho."},
               {"role": "user", "content": f"Context:\n{context}\n\nPregunta: {user_message}"}
           ]
       )["choices"][0]["message"]["content"]
       # Enviar la resposta per WhatsApp
       enviar_resposta(sender_id, resposta, phone_number_id)
   except Exception as e:
       print("Error:", e)
   return "OK", 200
# Enviar missatge per WhatsApp
def enviar_resposta(destinatari, text, phone_number_id):
   import requests
   whatsapp_token = os.environ["WHATSAPP_TOKEN"]
   url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
   headers = {
       "Authorization": f"Bearer {whatsapp_token}",
       "Content-Type": "application/json"
   }
   body = {
       "messaging_product": "whatsapp",
       "to": destinatari,
       "text": {
           "body": text
       }
   }
   requests.post(url, headers=headers, data=json.dumps(body))
# Inici de l'aplicació
if __name__ == "__main__":
   app.run(host="0.0.0.0", port=10000)
