
# utilisation_agent_existant.py
import os
from mistralai import Mistral
import importlib
import utils_classification 
importlib.reload(utils_classification)


client = Mistral(api_key="rTCf9RkFE3r7Bhfwjy5HVuTVRDZNgSAr")

# ID de l'agent existant (fourni par Mistral quand vous l'avez créé sur la plateforme)
AGENT_ID = "ag:df9c5c2b:20250918:untitled-agent:2a8b5efc"

def ask(text):
    response = client.beta.conversations.start(
    agent_id=AGENT_ID, inputs=text)
    return response
