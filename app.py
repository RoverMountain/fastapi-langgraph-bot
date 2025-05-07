# app.py

from fastapi import FastAPI, Request
from pydantic import BaseModel
from langgraph.graph import StateGraph
from langchain_openai import ChatOpenAI
from typing import TypedDict
import os
import httpx
import json
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

app = FastAPI()

# ======== MODELOS ========
class PerguntaRequest(BaseModel):
    mensagem: str

class RespostaResponse(BaseModel):
    resposta: str

# ======== CONFIGURAÇÃO DO LLM E GRAFO ========
llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0)

class State(TypedDict):
    mensagem: str
    resposta: str

async def chamar_llm(state: State) -> State:
    pergunta = state["mensagem"]
    resposta = await llm.ainvoke(pergunta)
    return {"resposta": resposta.content}

graph = StateGraph(State)
graph.add_node("chamar_llm", chamar_llm)
graph.set_entry_point("chamar_llm")
graph.set_finish_point("chamar_llm")
graph = graph.compile()

# ======== ENDPOINT MANUAL DE TESTE ========
@app.post("/perguntar", response_model=RespostaResponse)
async def perguntar(pergunta: PerguntaRequest):
    resultado = await graph.ainvoke({"mensagem": pergunta.mensagem})
    return {"resposta": resultado["resposta"]}

# ======== ENDPOINT WEBHOOK ========
@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    payload = await request.json()
    print("Webhook recebido do Whapi:\n", json.dumps(payload, indent=2, ensure_ascii=False)) # Log no Render

# Verifica se é um evento do tipo mensagem recebida
    event_type = payload.get("event", {}).get("event")
    if event_type != "post":
        print("Evento ignorado:", event_type)
        return {"status": "ignored"}

    messages = payload.get("messages", [])
    if not messages:
        print("Nenhuma mensagem encontrada no payload.")
        return {"status": "no message"}

    message_data = messages[0]
    message = message_data.get("text", {}).get("body")
    phone = message_data.get("from")

# Ignorar mensagens enviadas por você mesmo (from_me = True)
    if message_data.get("from_me", False):
        print("Mensagem enviada por mim mesmo ignorada.")
        return {"status": "ignored_self_message"}

    if not message or not phone:
        print("Payload inválido: mensagem ou telefone ausente.")
        return {"status": "invalid payload"}

    print(f"Mensagem recebida de {phone}: {message}")

    # Gerar resposta com LangGraph
    resposta_state = await graph.ainvoke({"mensagem": message})
    resposta = resposta_state["resposta"]
    print(f"Resposta gerada: {resposta}")

    # Enviar resposta de volta via Whapi
    whapi_url = "https://gate.whapi.cloud/messages/text"
    headers = {
        "Authorization": f"Bearer {os.getenv('WHAPI_API_KEY')}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(whapi_url, headers=headers, json={
                "to": phone,
                "body": resposta
            })

            print("Status da resposta do Whapi:", response.status_code)
            print("Conteúdo da resposta do Whapi:", response.text)

            if response.status_code != 200:
                return {"status": "erro_envio", "detalhe": response.text}

    except Exception as e:
        print("Erro ao tentar enviar mensagem via Whapi:", str(e))
        return {"status": "erro_http", "detalhe": str(e)}

    return {"status": "ok"}


