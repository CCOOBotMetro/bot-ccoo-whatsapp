import os
import requests
from flask import Flask, request
from openai import OpenAI
import faiss
import numpy as np
import pickle

app = Flask(__name__)

# Memòria temporal per controlar estat actiu del bot per cada usuari
usuaris_actius = {}

# Carrega FAISS + chunks
with open("index.pkl", "rb") as f:
    index = pickle.load(f)
with open("chunks.pkl", "rb") as f:
    chunk_texts = pickle.load(f)

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def enviar_missatge(destinatari, missatge):
    url = f"https://graph.facebook.com/v18.0/{os.environ['PHONE_NUMBER_ID']}/messages"
    headers = {
        "Authorization": f"Bearer {os.environ['WHATSAPP_TOKEN']}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": destinatari,
        "type": "text",
        "text": { "body": missatge }
    }
    requests.post(url, headers=headers, json=data)

def enviar_botons_inici(destinatari):
    url = f"https://graph.facebook.com/v18.0/{os.environ['PHONE_NUMBER_ID']}/messages"
    headers = {
        "Authorization": f"Bearer {os.environ['WHATSAPP_TOKEN']}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": destinatari,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": { "text": "Benvingut al bot de CCOO Metro! Selecciona una opció:" },
            "action": {
                "buttons": [
                    { "type": "reply", "reply": { "id": "opc1_permisos", "title": "Permisos" } },
                    { "type": "reply", "reply": { "id": "opc2_altres", "title": "Altres" } }
                ]
            }
        }
    }
    requests.post(url, headers=headers, json=data)

def enviar_botons_permisos(destinatari):
    permisos = [
        "Matrimoni", "Canvi de domicili", "Naixement", "Hospitalització",
        "Decés", "Exàmens", "Formació", "Trasllat", "Funcions públiques"
    ]
    botons = [
        { "type": "reply", "reply": { "id": f"perm_{i}", "title": t } }
        for i, t in enumerate(permisos)
    ]
    data = {
        "messaging_product": "whatsapp",
        "to": destinatari,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": { "text": "Selecciona un permís per consultar:" },
            "action": { "buttons": botons[:3] }  # Mostra els primers 3 (limitat per WhatsApp)
        }
    }
    url = f"https://graph.facebook.com/v18.0/{os.environ['PHONE_NUMBER_ID']}/messages"
    headers = {
        "Authorization": f"Bearer {os.environ['WHATSAPP_TOKEN']}",
        "Content-Type": "application/json"
    }
    requests.post(url, headers=headers, json=data)

def generar_resposta(pregunta):
    embedding = client.embeddings.create(
        input=pregunta,
        model="text-embedding-3-small"
    ).data[0].embedding
    D, I = index.search(np.array([embedding]).astype("float32"), 3)
    context = "\n---\n".join([chunk_texts[i] for i in I[0]])
    resposta = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Respon segons el context proporcionat. Si no tens prou informació, digues-ho."},
            {"role": "user", "content": f"Context:\n{context}\n\nPregunta: {pregunta}"}
        ]
    )
    return resposta.choices[0].message.content

@app.route("/", methods=["GET"])
def index():
    return "Bot viu!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    dades = request.get_json()
    try:
        message = dades["entry"][0]["changes"][0]["value"]["messages"][0]
        sender = message["from"]

        if "text" in message:
            text = message["text"]["body"].strip().lower()
            if text == "bot":
                usuaris_actius[sender] = True
                enviar_botons_inici(sender)
                return "OK", 200
            elif sender in usuaris_actius and usuaris_actius[sender]:
                if text == "no":
                    usuaris_actius.pop(sender, None)
                    enviar_missatge(sender, "D'acord. Si vols tornar a activar-me, escriu BOT.")
                else:
                    resposta = generar_resposta(text)
                    enviar_missatge(sender, resposta)
                return "OK", 200
            else:
                enviar_missatge(sender, "Per activar el bot escriu la paraula *BOT*.")
                return "OK", 200

        if "interactive" in message:
            inter = message["interactive"]
            if inter["type"] == "button_reply":
                resposta_id = inter["button_reply"]["id"]
                usuaris_actius[sender] = True

                if resposta_id == "opc1_permisos":
                    enviar_botons_permisos(sender)
                elif resposta_id == "opc2_altres":
                    enviar_missatge(sender, "Escriu la teva consulta i ens posarem en contacte.")
                elif resposta_id.startswith("perm_"):
                    permis_index = int(resposta_id.split("_")[1])
                    permis_nom = [
                        "matrimoni", "canvi de domicili", "naixement",
                        "hospitalització", "decés", "exàmens",
                        "formació", "trasllat", "funcions públiques"
                    ][permis_index]
                    resposta = generar_resposta(permis_nom)
                    enviar_missatge(sender, resposta)
                    enviar_missatge(sender, "Vols fer una altra consulta? (sí / no)")

                return "OK", 200

    except Exception as e:
        print("Error al webhook:", e)

    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
