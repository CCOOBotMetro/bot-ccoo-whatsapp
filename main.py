from flask import Flask, request
import requests
import os
from openai import OpenAI
app = Flask(__name__)
# Inicialitza client d'OpenAI
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
VERIFY_TOKEN = os.environ["VERIFY_TOKEN"]
WHATSAPP_TOKEN = os.environ["WHATSAPP_TOKEN"]
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
   if request.method == 'GET':
       if request.args.get('hub.verify_token') == VERIFY_TOKEN:
           return request.args.get('hub.challenge')
       return 'Verificació fallida', 403
   if request.method == 'POST':
       data = request.get_json()
       try:
           message = data['entry'][0]['changes'][0]['value']['messages'][0]
           sender = message['from']
           text = message['text']['body']
           # Consulta a OpenAI
           resposta = client.chat.completions.create(
               model="gpt-3.5-turbo",
               messages=[
                   {"role": "system", "content": "Respon com a assistent sindical. Si no tens prou informació, digues-ho."},
                   {"role": "user", "content": text}
               ]
           ).choices[0].message.content
           # Enviar resposta a WhatsApp
           enviar_resposta(sender, resposta)
       except Exception as e:
           print("Error:", e)
       return 'OK', 200
def enviar_resposta(telefon, missatge):
   url = "https://graph.facebook.com/v18.0/580162021858021/messages"
   headers = {
       "Authorization": f"Bearer {WHATSAPP_TOKEN}",
       "Content-Type": "application/json"
   }
   payload = {
       "messaging_product": "whatsapp",
       "to": telefon,
       "type": "text",
       "text": {"body": missatge}
   }
   requests.post(url, headers=headers, json=payload)
if __name__ == '__main__':
   app.run(host='0.0.0.0', port=10000)
