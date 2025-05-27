import os
import requests
import pickle
import faiss
import numpy as np
from flask import Flask, request
from openai import OpenAI
from datetime import datetime

app = Flask(__name__)
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

with open("index.pkl", "rb") as f:
    index = pickle.load(f)
with open("chunks.pkl", "rb") as f:
    chunk_texts = pickle.load(f)

assert hasattr(index, "search"), "L'objecte FAISS no és vàlid."

user_sessions = {}
PERMISOS_LISTA = [
    "Matrimoni", "Canvi de domicili", "Naixement i cura de menor",
    "Visites mèdiques", "Exàmens oficials", "Defunció de familiar",
    "Assumptes propis", "Deures públics", "Judici per empresa",
    "Cura fills menors", "Lactància acumulada", "Reducció de jornada",
    "Exàmens prenatals", "Sense sou", "Violència de gènere",
    "Assistència mèdica familiars", "Adopció / acolliment", "Jubilació parcial"
]

def detectar_idioma(text):
    esp = ["permiso", "consulta", "gracias", "usted", "quiero", "otra"]
    return "es" if any(p in text.lower() for p in esp) else "ca"

def missatge_benvinguda(lang):
    if lang == "es":
        return (
            "Bienvenido/a al asistente virtual de CCOO Metro de Barcelona.\n\n"
            "Estoy aquí para ayudarte a resolver tus dudas.\n"
            "Selecciona una de las siguientes opciones:\n\n"
            "1 - Permisos laborales\n"
            "2 - Otras consultas\n\n"
            "Escribe el número o el nombre de la opción que quieres consultar."
        )
    return (
        "Benvingut/da a l'assistent virtual de CCOO Metro de Barcelona.\n\n"
        "Soc aquí per ajudar-te a resoldre dubtes.\n"
        "Selecciona una de les següents opcions:\n\n"
        "1 - Permisos laborals\n"
        "2 - Altres consultes\n\n"
        "Escriu a continuació el número o el nom de l'opció que vols consultar."
    )

def text_nova_consulta(lang):
    return "¿Quieres realizar otra consulta? (sí / no)" if lang == "es" else "Vols fer una nova consulta? (sí / no)"

def text_descarregar_pdf(lang):
    return "¿Quieres descargar la tabla oficial de permisos? (sí / no)" if lang == "es" else "Vols descarregar la taula oficial de permisos? (sí / no)"

def text_final(lang):
    return (
        "Gracias por utilizar el asistente virtual de CCOO.\nSi más adelante quieres hacer otra consulta, escribe la palabra CCOO."
        if lang == "es" else
        "Gràcies per utilitzar l'assistent virtual de CCOO.\nSi més endavant vols tornar a fer una consulta, escriu la paraula CCOO."
    )

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
        "text": {"body": missatge}
    }
    requests.post(url, headers=headers, json=data)

def enviar_document(destinatari):
    url = f"https://graph.facebook.com/v18.0/{os.environ['PHONE_NUMBER_ID']}/messages"
    headers = {
        "Authorization": f"Bearer {os.environ['WHATSAPP_TOKEN']}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": destinatari,
        "type": "document",
        "document": {
            "id": "1011069024514667",
            "filename": "Quadre_permisos_FMB.pdf"
        }
    }
    requests.post(url, headers=headers, json=data)

def generar_resposta(pregunta):
    try:
        embedding = client.embeddings.create(
            input=pregunta,
            model="text-embedding-ada-002"
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

    except Exception as e:
        print("Error generant la resposta:", str(e))
        return "Ho sento, ha fallat la generació de la resposta."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


main.py regenerat i corregit amb:

Canvi del model d’embeddings a text-embedding-ada-002.

Impressió clara de l’error si falla la generació de la resposta (print("Error generant la resposta:", str(e))).


Ara pots tornar a desplegar el bot a Render i provar de fer una consulta com “Exàmens oficials” o “Permís per matrimoni”. Si torna a fallar, copia aquí exactament el que apareix al log.

Anem pel bon camí!

