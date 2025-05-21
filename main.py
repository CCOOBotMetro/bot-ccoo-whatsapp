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

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

with open("index.pkl", "rb") as f:
   index = pickle.load(f)
with open("chunks.pkl", "rb") as f:
   chunk_texts = pickle.load(f)

app = Flask(__name__)
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "botfmb2025")

# Estat de cada usuari
usuaris = {}

# Paraules de salutació reconegudes
salutacions = {"hola", "bon dia", "bona tarda", "bona nit", "hello", "ei", "bones"}

# Textos
intro = "Gràcies per contactar amb CCOO de Metro de Barcelona, soc el BOT Virtual i soc aquí per ajudar-te a resoldre els teus dubtes. A continuació et detallaré un índex de la informació que disposo:"
index_text = "1 – Permisos\n2 – Altres"
comiat = "Moltes gràcies per contactar amb CCOO. Si necessites ajuda en un futur, escriu BOT per tornar-me a activar."
email_altres = "Pots escriure'ns també a ccoometro@tmb.cat si ho prefereixes."

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
                       text = message.get("text", {}).get("body", "").strip().lower()

                       estat = usuaris.get(sender, {"fase": "inicial", "idioma": "ca"})

                       if text == "bot":
                           usuaris[sender] = {"fase": "index", "idioma": "ca"}
                           enviar_missatge(sender, intro + "\n" + index_text, phone_number_id)
                           return "OK", 200

                       if estat["fase"] == "inicial" and any(sal in text for sal in salutacions):
                           usuaris[sender] = {"fase": "index", "idioma": "ca"}
                           enviar_missatge(sender, intro + "\n" + index_text, phone_number_id)
                           return "OK", 200

                       if estat["fase"] == "index":
                           if "1" in text or "perm" in text:
                               usuaris[sender]["fase"] = "permis_llista"
                               llista = "\n".join([f"{i+1}. Permís {i+1}" for i in range(18)])
                               enviar_missatge(sender, "Aquest és el llistat de permisos disponibles:\n" + llista, phone_number_id)
                               return "OK", 200
                           elif "2" in text or "altres" in text:
                               usuaris[sender]["fase"] = "altres_consulta"
                               enviar_missatge(sender, "Escriu el tipus de consulta que tens i en breu ens posarem en contacte amb tu.\n" + email_altres, phone_number_id)
                               return "OK", 200

                       if estat["fase"] == "permis_llista":
                           try:
                               num = int(text)
                               if 1 <= num <= 18:
                                   embedding = client.embeddings.create(input=f"Permís {num}", model="text-embedding-3-small").data[0].embedding
                                   D, I = index.search(np.array([embedding]).astype("float32"), 1)
                                   resposta = chunk_texts[I[0][0]]
                                   usuaris[sender]["fase"] = "permis_resposta"
                                   usuaris[sender]["ultim_perm"] = resposta
                                   enviar_missatge(sender, resposta + "\nVols descarregar la taula oficial de permisos?", phone_number_id)
                                   return "OK", 200
                           except:
                               enviar_missatge(sender, "Si us plau, escriu el número del permís que vols consultar (1 al 18).", phone_number_id)
                               return "OK", 200

                       if estat["fase"] == "permis_resposta":
                           if "sí" in text or "si" in text:
                               enviar_document(sender, phone_number_id)
                               usuaris[sender]["fase"] = "consulta_nova"
                               enviar_missatge(sender, "Vols fer una nova consulta?", phone_number_id)
                               return "OK", 200
                           elif "no" in text:
                               usuaris[sender]["fase"] = "consulta_nova"
                               enviar_missatge(sender, "Vols fer una nova consulta?", phone_number_id)
                               return "OK", 200

                       if estat["fase"] == "consulta_nova":
                           if "sí" in text or "si" in text:
                               usuaris[sender]["fase"] = "index"
                               enviar_missatge(sender, index_text, phone_number_id)
                               return "OK", 200
                           elif "no" in text:
                               usuaris[sender]["fase"] = "inicial"
                               enviar_missatge(sender, comiat, phone_number_id)
                               return "OK", 200

                       if estat["fase"] == "altres_consulta":
                           usuaris[sender]["fase"] = "consulta_nova"
                           enviar_missatge(sender, "Gràcies. Vols fer una nova consulta?", phone_number_id)
                           return "OK", 200

   return "OK", 200

def enviar_missatge(destinatari, missatge, phone_number_id):
   url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
   headers = {
       "Authorization": f"Bearer {os.environ['WHATSAPP_TOKEN']}",
       "Content-Type": "application/json"
   }
   data = {
       "messaging_product": "whatsapp",
       "to": destinatari,
       "type": "text",
       "text": {"body": missatge[:4096]}
   }
   requests.post(url, headers=headers, json=data)

def enviar_document(destinatari, phone_number_id):
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
   requests.post(url, headers=headers, json=data)

if __name__ == "__main__":
   app.run(host="0.0.0.0", port=5000) import os
import json
import pickle
import numpy as np
import faiss
import requests
from flask import Flask, request
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

with open("index.pkl", "rb") as f:
   index = pickle.load(f)
with open("chunks.pkl", "rb") as f:
   chunk_texts = pickle.load(f)

app = Flask(__name__)
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "botfmb2025")

# Estat de cada usuari
usuaris = {}

# Paraules de salutació reconegudes
salutacions = {"hola", "bon dia", "bona tarda", "bona nit", "hello", "ei", "bones"}

# Textos
intro = "Gràcies per contactar amb CCOO de Metro de Barcelona, soc el BOT Virtual i soc aquí per ajudar-te a resoldre els teus dubtes. A continuació et detallaré un índex de la informació que disposo:"
index_text = "1 – Permisos\n2 – Altres"
comiat = "Moltes gràcies per contactar amb CCOO. Si necessites ajuda en un futur, escriu BOT per tornar-me a activar."
email_altres = "Pots escriure'ns també a ccoometro@tmb.cat si ho prefereixes."

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
                       text = message.get("text", {}).get("body", "").strip().lower()

                       estat = usuaris.get(sender, {"fase": "inicial", "idioma": "ca"})

                       if text == "bot":
                           usuaris[sender] = {"fase": "index", "idioma": "ca"}
                           enviar_missatge(sender, intro + "\n" + index_text, phone_number_id)
                           return "OK", 200

                       if estat["fase"] == "inicial" and any(sal in text for sal in salutacions):
                           usuaris[sender] = {"fase": "index", "idioma": "ca"}
                           enviar_missatge(sender, intro + "\n" + index_text, phone_number_id)
                           return "OK", 200

                       if estat["fase"] == "index":
                           if "1" in text or "perm" in text:
                               usuaris[sender]["fase"] = "permis_llista"
                               llista = "\n".join([f"{i+1}. Permís {i+1}" for i in range(18)])
                               enviar_missatge(sender, "Aquest és el llistat de permisos disponibles:\n" + llista, phone_number_id)
                               return "OK", 200
                           elif "2" in text or "altres" in text:
                               usuaris[sender]["fase"] = "altres_consulta"
                               enviar_missatge(sender, "Escriu el tipus de consulta que tens i en breu ens posarem en contacte amb tu.\n" + email_altres, phone_number_id)
                               return "OK", 200

                       if estat["fase"] == "permis_llista":
                           try:
                               num = int(text)
                               if 1 <= num <= 18:
                                   embedding = client.embeddings.create(input=f"Permís {num}", model="text-embedding-3-small").data[0].embedding
                                   D, I = index.search(np.array([embedding]).astype("float32"), 1)
                                   resposta = chunk_texts[I[0][0]]
                                   usuaris[sender]["fase"] = "permis_resposta"
                                   usuaris[sender]["ultim_perm"] = resposta
                                   enviar_missatge(sender, resposta + "\nVols descarregar la taula oficial de permisos?", phone_number_id)
                                   return "OK", 200
                           except:
                               enviar_missatge(sender, "Si us plau, escriu el número del permís que vols consultar (1 al 18).", phone_number_id)
                               return "OK", 200

                       if estat["fase"] == "permis_resposta":
                           if "sí" in text or "si" in text:
                               enviar_document(sender, phone_number_id)
                               usuaris[sender]["fase"] = "consulta_nova"
                               enviar_missatge(sender, "Vols fer una nova consulta?", phone_number_id)
                               return "OK", 200
                           elif "no" in text:
                               usuaris[sender]["fase"] = "consulta_nova"
                               enviar_missatge(sender, "Vols fer una nova consulta?", phone_number_id)
                               return "OK", 200

                       if estat["fase"] == "consulta_nova":
                           if "sí" in text or "si" in text:
                               usuaris[sender]["fase"] = "index"
                               enviar_missatge(sender, index_text, phone_number_id)
                               return "OK", 200
                           elif "no" in text:
                               usuaris[sender]["fase"] = "inicial"
                               enviar_missatge(sender, comiat, phone_number_id)
                               return "OK", 200

                       if estat["fase"] == "altres_consulta":
                           usuaris[sender]["fase"] = "consulta_nova"
                           enviar_missatge(sender, "Gràcies. Vols fer una nova consulta?", phone_number_id)
                           return "OK", 200

   return "OK", 200

def enviar_missatge(destinatari, missatge, phone_number_id):
   url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
   headers = {
       "Authorization": f"Bearer {os.environ['WHATSAPP_TOKEN']}",
       "Content-Type": "application/json"
   }
   data = {
       "messaging_product": "whatsapp",
       "to": destinatari,
       "type": "text",
       "text": {"body": missatge[:4096]}
   }
   requests.post(url, headers=headers, json=data)

def enviar_document(destinatari, phone_number_id):
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
   requests.post(url, headers=headers, json=data)

if __name__ == "__main__":
   app.run(host="0.0.0.0", port=5000) 
