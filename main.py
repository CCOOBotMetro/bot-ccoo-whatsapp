from flask import Flask, request
import os
import json
import requests
app = Flask(__name__)
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
@app.route("/webhook", methods=["GET"])
def verify():
   if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.verify_token") == VERIFY_TOKEN:
       return request.args.get("hub.challenge"), 200
   return "Error de verificació", 403
@app.route("/webhook", methods=["POST"])
def webhook():
   data = request.get_json()
   print("Dades rebudes:", json.dumps(data, indent=2))
   try:
       entry = data["entry"][0]
       change = entry["changes"][0]
       message = change["value"]["messages"][0]
       sender_id = message["from"]
       phone_number_id = change["value"]["metadata"]["phone_number_id"]
       enviar_missatge(sender_id, phone_number_id, "Hola! El bot està funcionant correctament.")
   except Exception as e:
       print("Error:", e)
   return "OK", 200
def enviar_missatge(destinatari, phone_number_id, text):
   url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
   headers = {
       "Authorization": f"Bearer {WHATSAPP_TOKEN}",
       "Content-Type": "application/json"
   }
   payload = {
       "messaging_product": "whatsapp",
       "to": destinatari,
       "type": "text",
       "text": {
           "body": text
       }
   }
   response = requests.post(url, headers=headers, data=json.dumps(payload))
   print("Resposta Meta:", response.text)
if __name__ == "__main__":
   app.run(host="0.0.0.0", port=10000)
