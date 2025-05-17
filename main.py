import os
import json
import pickle
from flask import Flask, request
from openai import OpenAI
from dotenv import load_dotenv
# Carrega les variables d'entorn
load_dotenv()
# Inicialitza el client OpenAI
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
# Inicialitza Flask
app = Flask(__name__)
# Carrega l'índex i els fragments de text
with open("index.pkl", "rb") as f:
   index = pickle.load(f)
with open("chunks.pkl", "rb") as f:
   chunks = pickle.load(f)
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "botfmb2025")
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
   if data["object"] == "whatsapp_business_account":
       for entry in data.get("entry", []):
           for change in entry.get("changes", []):
               value = change.get("value", {})
               messages = value.get("messages", [])
               if messages:
                   for message in messages:
                       phone_number_id = value["metadata"]["phone_number_id"]
                       sender = message["from"]
                       text = message.get("text", {}).get("body", "")
                       # Cerca el context rellevant al text rebut
                       embedding = client.embeddings.create(
                           model="text-embedding-ada-002",
                           input=text
                       ).data[0].embedding
                       import numpy as np
                       D, I = index.search(np.array([embedding], dtype="float32"), k=5)
                       context = "\n\n".join([chunks[i] for i in I[0]])
                       # Genera la resposta amb OpenAI
                       resposta = client.chat.completions.create(
                           model="gpt-3.5-turbo",
                           messages=[
                               {"role": "system", "content": f"Contesta només amb la informació següent:\n\n{context}"},
                               {"role": "user", "content": text}
                           ]
                       ).choices[0].message.content
                       # Envia la resposta per WhatsApp
                       enviar_missatge_whatsapp(sender, resposta, phone_number_id)
   return "OK", 200
def enviar_missatge_whatsapp(destinatari, missatge, phone_number_id):
   import requests
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
   print("Resposta enviada:", response.status_code, response.text)
if __name__ == "__main__":
   app.run(host="0.0.0.0", port=10000)
