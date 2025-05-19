import os
import pickle
import numpy as np
import faiss
import openai
from docx import Document
from google.colab import drive

# PAS 1: Muntar Google Drive
drive.mount('/content/drive')

# PAS 2: Configura la clau d'OpenAI
client = openai.OpenAI(api_key="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")

# PAS 3: Llegir el document .docx
file_path = "/content/drive/MyDrive/bot_fmb_docs/PERMISOS v2.docx"
def load_docx_text(path):
    doc = Document(path)
    text = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
    return "\n".join(text)

text = load_docx_text(file_path)

# PAS 4: Fragmentar el text en trossos
def split_text(text, max_words=200):
    import re
    sentences = re.split(r'(?<=[.!?]) +', text)
    chunks, chunk, count = [], "", 0
    for sentence in sentences:
        words = sentence.split()
        if count + len(words) > max_words:
            chunks.append(chunk.strip())
            chunk = sentence + " "
            count = len(words)
        else:
            chunk += sentence + " "
            count += len(words)
    if chunk:
        chunks.append(chunk.strip())
    return chunks

chunks = split_text(text)
print(f"S'han generat {len(chunks)} fragments.")

# PAS 5: Crear embeddings amb el nou client
embeddings = []
for chunk in chunks:
    response = client.embeddings.create(
        input=chunk,
        model="text-embedding-3-small"
    )
    embeddings.append(response.data[0].embedding)

# PAS 6: Crear index FAISS
embedding_matrix = np.array(embeddings).astype("float32")
index = faiss.IndexFlatL2(len(embedding_matrix[0]))
index.add(embedding_matrix)

# PAS 7: Desa arxius
with open("index.pkl", "wb") as f:
    pickle.dump(index, f)

with open("chunks.pkl", "wb") as f:
    pickle.dump(chunks, f)

print("Tot fet! Ara pots descarregar index.pkl i chunks.pkl")
