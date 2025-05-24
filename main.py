import os
import requests
from flask import Flask, request
from openai import OpenAI
import faiss
import numpy as np
import pickle

app = Flask(__name__)

usuaris_actius = {}
estat_usuari = {}

# Càrrega de dades
with open("index.pkl", "rb") as f:
    index = pickle.load(f)
with open("chunks.pkl", "rb") as f:
    chunk_texts = pickle.load(f)

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# Missatges
def enviar_missatge(destinatari, text):
    url = f"https://graph.facebook.com/v18.0/{os.environ['PHONE_NUMBER_ID']}/messages"
    headers = {
        "Authorization": f"Bearer {os.environ['WHATSAPP_TOKEN']}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": destinatari,
        "type": "text",
        "text": {"body": text}
    }
    requests.post(url, headers=headers, json=data)

# Menú inicial
def enviar_menu_inicial(destinatari):
    missatge = (
        "Gràcies per contactar amb CCOO de Metro de Barcelona. Soc el BOT virtual i soc aquí per ajudar-te.\n\n"
        "Selecciona una opció:\n"
        "1 - Permisos\n"
        "2 - Altres"
    )
    enviar_missatge(destinatari, missatge)
    estat_usuari[destinatari] = "menu"

# Llistat de permisos
llista_permisos = [
    "Matrimoni",
    "Canvi de domicili",
    "Naixement i cura de menor",
    "Hospitalització o accident",
    "Defunció de familiar",
    "Deures públics o sindicals",
    "Funcions electorals",
    "Trasllat de domicili",
    "Conciliació familiar",
    "Formació professional",
    "Permís retribuït per lactància",
    "Reducció de jornada",
    "Permís per exàmens",
    "Permís sense sou",
    "Permís per violència de gènere",
    "Permís per assistència mèdica",
    "Permís per adopció o acollida",
    "Permís per jubilació anticipada"
]

def enviar_llistat_permisos(destinatari):
    llistat = "\n".join([f"{i+1} - {p}" for i, p in enumerate(llista_permisos)])
    enviar_missatge(destinatari, f"Quin permís vols consultar?\n\n{llistat}")
    estat_usuari[destinatari] = "esperant_permís"

# Resposta amb OpenAI
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

# Flask routes
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
                enviar_menu_inicial(sender)
                return "OK", 200

            if sender not in usuaris_actius or not usuaris_actius[sender]:
                enviar_missatge(sender, "Per activar el bot escriu la paraula *BOT*.")
                return "OK", 200

            estat = estat_usuari.get(sender, "")

            if text == "no":
                usuaris_actius.pop(sender, None)
                estat_usuari.pop(sender, None)
                enviar_missatge(sender, "D'acord! Si vols tornar a activar-me, escriu *BOT*.")
                return "OK", 200

            if estat == "menu":
                if text in ["1", "permisos"]:
                    enviar_llistat_permisos(sender)
                elif text in ["2", "altres"]:
                    enviar_missatge(sender, "Escriu la teva consulta i ens posarem en contacte.")
                else:
                    enviar_missatge(sender, "Opció no reconeguda. Escriu 1 o 2.")
                return "OK", 200

            if estat == "esperant_permís":
                try:
                    idx = int(text) - 1
                    if 0 <= idx < len(llista_permisos):
                        consulta = llista_permisos[idx]
                    else:
                        raise ValueError
                except:
                    consulta = text
                resposta = generar_resposta(consulta)
                enviar_missatge(sender, resposta)
                enviar_missatge(sender, "Vols fer una altra consulta? (sí / no)")
                estat_usuari[sender] = "menu"
                return "OK", 200

    except Exception as e:
        print("ERROR al webhook:", e)

    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
