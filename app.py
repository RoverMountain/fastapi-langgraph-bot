# app.py

from fastapi import FastAPI
from pydantic import BaseModel
from langgraph.graph import StateGraph
from langchain_openai import ChatOpenAI
from typing import TypedDict
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

app = FastAPI()

class PerguntaRequest(BaseModel):
    mensagem: str

class RespostaResponse(BaseModel):
    resposta: str

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

@app.post("/perguntar", response_model=RespostaResponse)
async def perguntar(pergunta: PerguntaRequest):
    resultado = await graph.ainvoke({"mensagem": pergunta.mensagem})
    return {"resposta": resultado["resposta"]}

from fastapi import Request
import httpx
import os

# Endpoint Webhook
@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    payload = await request.json()

    # Garante que é um evento de mensagem recebida
    if payload.get("event") != "message:received":
        return {"status": "ignored"}

    data = payload.get("data", {})
    message = data.get("text")
    phone = data.get("from")

    if not message or not phone:
        return {"status": "invalid payload"}

    # Gera resposta com LangGraph
    resposta_state = await graph.ainvoke({"mensagem": message})
    resposta = resposta_state["resposta"]

    # Envia resposta de volta usando API Whapi
    whapi_url = "https://gate.whapi.cloud/messages/text"
    headers = {
        "Authorization": f"Bearer {os.getenv('WHAPI_API_KEY')}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        await client.post(whapi_url, headers=headers, json={
            "to": phone,
            "body": resposta
        })

    return {"status": "ok"}
