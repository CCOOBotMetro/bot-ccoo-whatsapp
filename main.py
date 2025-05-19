import os import json import pickle import numpy as np import faiss import requests from flask import Flask, request from openai import OpenAI from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

with open("index.pkl", "rb") as f: index = pickle.load(f) with open("chunks.pkl", "rb") as f: chunk_texts = pickle.load(f)

ultim_fragment = {} document_enviat = set() estat_usuari = {}

app = Flask(name) VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "botfmb2025")

@app.route("/webhook", methods=["GET"]) def verify(): token = request.args.get("hub.verify_token") challenge = request.args.get("hub.challenge") if token == VERIFY_TOKEN: return challenge return "Verificació fallida", 403

@app.route("/webhook", methods=["POST"]) def webhook(): data = request.get_json() if data.get("object") == "whatsapp_business_account": for entry in data.get("entry", []): for change in entry.get("changes", []): value = change.get("value", {}) messages = value.get("messages", []) if messages: for message in messages: phone_number_id = value["metadata"]["phone_number_id"] sender = message["from"] text = message.get("text", {}).get("body", "").strip().lower()

# Reactiva el bot
                    if text == "bot":
                        estat_usuari[sender] = "actiu"
                        enviar_missatge_whatsapp(sender, "Bot reactivat! Pots fer-me una nova consulta.", phone_number_id)
                        return "OK", 200

                    # Si l'usuari està "desconnectat", ignorar fins que escrigui "bot"
                    if estat_usuari.get(sender) == "desconnectat":
                        return "OK", 200

                    # Si ja ha dit "sí" per descarregar, evitem repetir
                    if text in ["sí", "si"] and sender in ultim_fragment:
                        if sender not in document_enviat:
                            enviar_document_whatsapp(sender, phone_number_id)
                            document_enviat.add(sender)
                        return "OK", 200

                    # Si l'usuari diu que no vol res més
                    if text in ["no", "gràcies", "res", "gracias"]:
                        enviar_missatge_whatsapp(sender, "D'acord, desconnecto el bot. Si necessites res més, escriu BOT per tornar a activar-lo.", phone_number_id)
                        estat_usuari[sender] = "desconnectat"
                        return "OK", 200

                    # Embedding i cerca
                    embedding = client.embeddings.create(
                        input=text,
                        model="text-embedding-3-small"
                    ).data[0].embedding

                    D, I = index.search(np.array([embedding]).astype("float32"), 1)
                    fragment = chunk_texts[I[0][0]]

                    # Simplicitat: si la distància és massa alta, no responem
                    if D[0][0] > 0.6:
                        missatge = "No disposo d'aquesta informació concreta, però pròximament ens posarem en contacte per respondre el teu dubte.\nNecessites alguna cosa més?"
                        estat_usuari[sender] = "esperant_comiat"
                        enviar_missatge_whatsapp(sender, missatge, phone_number_id)
                        return "OK", 200

                    # Resposta literal
                    ultim_fragment[sender] = fragment
                    enviar_missatge_whatsapp(sender, fragment, phone_number_id)

                    # Oferim document PDF només si no l'ha rebut
                    if sender not in document_enviat:
                        enviar_missatge_whatsapp(sender, "Vols descarregar el document oficial de permisos?", phone_number_id)

return "OK", 200

def enviar_missatge_whatsapp(destinatari, missatge, phone_number_id): url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages" headers = { "Authorization": f"Bearer {os.environ['WHATSAPP_TOKEN']}", "Content-Type": "application/json" } data = { "messaging_product": "whatsapp", "to": destinatari, "type": "text", "text": {"body": missatge[:4096]} } requests.post(url, headers=headers, json=data)

def enviar_document_whatsapp(destinatari, phone_number_id): url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages" headers = { "Authorization": f"Bearer {os.environ['WHATSAPP_TOKEN']}", "Content-Type": "application/json" } data = { "messaging_product": "whatsapp", "to": destinatari, "type": "document", "document": { "id": "637788649308962", "filename": "Quadre_permisos_FMB_10112023.pdf" } } requests.post(url, headers=headers, json=data)

if name == "main": app.run(host="0.0.0.0", port=5000)

