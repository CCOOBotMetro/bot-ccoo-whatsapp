import os
import json
import pickle
import numpy as np
import faiss
import requests
from flask import Flask, request
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
# Inicialitza el client OpenAI
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
# Carrega l’índex i els trossos
with open("index.pkl", "rb") as f:
   index = pickle.load(f)
with open("chunks.pkl", "rb") as f:
   chunk_texts = pickle.load(f)
# Inicialitza Flask
app = Flask(__name__)
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
                       text = message.get("text", {}).get("body", "").strip().lower()
                       # Si és un missatge de benvinguda
                       if text in ["hola", "hola!", "bon dia", "bon dia!", "bona tarda", "bona tarda!", "bona nit", "bona nit!", "¡hola!", "¡bon dia!", "¡bona tarda!", "¡bona nit!"]:
                           enviar_missatge_whatsapp(sender, "Hola! Sóc el bot informatiu de CCOO. Pots fer-me preguntes sobre permisos, convenis o condicions laborals. Respondré segons la informació oficial disponible.", phone_number_id)
                           return "OK", 200
                       # Si l’usuari vol descarregar el document
                       if text in ["sí", "si", "sí!", "si!", "s", "s!"]:
                           enviar_document_whatsapp(sender, phone_number_id)
                           return "OK", 200
                       # Generar embedding
                       embedding = client.embeddings.create(
                           input=text,
                           model="text-embedding-3-small"
                       ).data[0].embedding
                       # Buscar trossos més rellevants
                       D, I = index.search(np.array([embedding]).astype("float32"), 3)
                       context = "\n---\n".join([chunk_texts[i] for i in I[0]])
                       # Fer la crida a OpenAI
                       resposta = client.chat.completions.create(
                           model="gpt-3.5-turbo",
                           messages=[
                               {"role": "system", "content": f"Contesta només amb la informació següent:\n\n{context}"},
                               {"role": "user", "content": text}
                           ]
                       ).choices[0].message.content
                       # Enviar resposta
                       enviar_missatge_whatsapp(sender, resposta, phone_number_id)
                       # Preguntar si vol descarregar el document
                       enviar_missatge_whatsapp(sender, "Vols descarregar el document oficial de permisos?", phone_number_id)
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
def enviar_document_whatsapp(destinatari, phone_number_id):
   url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
   headers = {
       "Authorization": f"Bearer {os.environ['WHATSAPP_TOKEN']}",
       "Content-Type": "application/json"
   }
   data = {
       "messaging_product": "whatsapp",
       "to": destinatari,
       "type": "document",
       "document": {
           "id": "637788649308962",
           "filename": "Quadre_permisos_FMB_10112023.pdf"
       }
   }
   response = requests.post(url, headers=headers, json=data)
   print("Document enviat:", response.status_code, response.text)
if __name__ == "__main__":
   app.run(host="0.0.0.0", port=5000)
