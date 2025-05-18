import os
import json
from flask import Flask, request
from openai import OpenAI
from dotenv import load_dotenv
import requests
load_dotenv()
# Inicialitza el client OpenAI
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
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
                       text = message.get("text", {}).get("body", "").strip()
                       # Comprova si és un missatge de salutació inicial
                       salutacions = ["hola", "bon dia", "hello"]
                       if any(s in text.lower() for s in salutacions):
                           resposta = (
                               "Hola! Sóc el bot informatiu de CCOO. "
                               "Pots fer-me preguntes sobre permisos, convenis o condicions laborals. "
                               "Respondré segons la informació oficial disponible."
                           )
                           enviar_missatge_whatsapp(sender, resposta, phone_number_id)
                           return "OK", 200  # No fem cap consulta a OpenAI
                       # Si no és salutació, consultem OpenAI
                       resposta = client.chat.completions.create(
                           model="gpt-3.5-turbo",
                           messages=[
                               {"role": "system", "content": "Respon només amb la informació següent:\n\n{context}"},
                               {"role": "user", "content": text}
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
   print("Resposta enviada:", response.status_code, response.text)
if __name__ == "__main__":
   app.run(host="0.0.0.0", port=5000)
