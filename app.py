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
    data = await request.json()
    
    try:
        message = data['message']
        phone = data['phone']
    except KeyError:
        return {"status": "invalid payload"}

    # Processa com LangGraph
    resposta_state = await graph.ainvoke({"mensagem": message})
    resposta = resposta_state["resposta"]

    # Monta URL correta da Z-API
    zap_api_url = f"https://api.z-api.io/instances/{'3E07F87D8FA3703AE7AE96E82C2DBF10'}/token/{'0EFC31466D9AE414CB5B9E2A'}/send-messages"

    async with httpx.AsyncClient() as client:
        await client.post(zap_api_url, json={
            "phone": phone,
            "message": resposta
        })

    return {"status": "ok"}