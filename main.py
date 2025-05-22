import os
import requests
from flask import Flask, request
from openai import OpenAI
import faiss
import numpy as np
import pickle

app = Flask(__name__)

# Carreguem l'índex i els chunks
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
        "text": {
            "body": missatge
        }
    }
    requests.post(url, headers=headers, json=data)

def enviar_botons_interactius(destinatari):
    url = f"https://graph.facebook.com/v18.0/{os.environ['PHONE_NUMBER_ID']}/messages"
