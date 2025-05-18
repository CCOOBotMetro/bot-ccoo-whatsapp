import os
import json
from flask import Flask, request
from openai import OpenAI
from dotenv import load_dotenv
import requests
load_dotenv()
# Inicialitza OpenAI
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "botfmb2025")
# Inicialitza Flask
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
                       # Llistat de missatges inicials (salutacions)
                       MISSATGES_INICIALS = {
                           "hola", "hola!", "¡hola!",
                           "bon dia", "bon dia!", "¡bon dia!",
                           "bona tarda", "bona tarda!", "¡bona tarda!",
                           "bona nit", "bona nit!", "¡bona nit!",
                           "ei", "bones", "què tal", "com estàs",
                           "hello", "hi", "hey", "prueba", "test", "ping", "hola bot"
                       }
                       if text in MISSATGES_INICIALS:
                           resposta = (
                               "Hola! Sóc el bot informatiu de CCOO. "
                               "Pots fer-me preguntes sobre permisos, convenis o condicions laborals. "
                               "Respondré segons la informació oficial disponible."
                           )
                           enviar_missatge_whatsapp(sender, resposta, phone_number_id)
                           return "OK", 200  # Aturem aquí
                       # Consulta OpenAI només si no és una salutació
                       resposta = client.chat.completions.create(
                           model="gpt-3.5-turbo",
                           messages=[
                               {"role": "system", "content": "Respon només amb informació oficial proporcionada per CCOO. Si no tens dades suficients, indica-ho."},
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
