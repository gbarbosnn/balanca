from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Optional
import asyncio

app = FastAPI()

# Permitir requisições do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

produtos = {
    "Arroz Premium": 0.500,
    "Feijão Carioca": 1.000,
    "Coca-Cola 2L": 2.000,
    "Banana Prata": 1.000,
    "Pão Francês": 1.000,
    "Contra Filé": 1.000
}

carrinhos_ws: Dict[str, WebSocket] = {}
carrinhos_itens: Dict[str, Dict[str, int]] = {}
pesos_atuais: Dict[str, float] = {}

class ProdutoSelecionado(BaseModel):
    nome: str
    acao: str
    quantidade: int = 1

@app.websocket("/carrinho/{id}")
async def conectar_esp32(websocket: WebSocket, id: str):
    await websocket.accept()
    carrinhos_ws[id] = websocket
    carrinhos_itens.setdefault(id, {})
    print(f"Carrinho {id} conectado")

    try:
        while True:
            mensagem = await websocket.receive_json()
            print(mensagem)
            peso = mensagem.get("peso")
            if peso is not None:
                print(f"Peso recebido do carrinho {id}: {peso} kg")
                pesos_atuais[id] = peso
                print("Pesos atuais:", pesos_atuais)
    except WebSocketDisconnect:
        print(f"ESP32 {id} desconectado.")
        carrinhos_ws.pop(id, None)
        carrinhos_itens.pop(id, None)
        pesos_atuais.pop(id, None)

@app.post("/carrinho/{id}/produto")
async def adicionar_produto(id: str, produto: ProdutoSelecionado):
    if produto.nome not in produtos:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    if id not in carrinhos_ws:
        raise HTTPException(status_code=400, detail="Carrinho não conectado")

    print(f"Produto '{produto.nome}' ({produto.quantidade}) solicitado para carrinho {id}")

    # Solicita o peso atual
    websocket = carrinhos_ws[id]
    await websocket.send_json({"acao": "enviar_peso"})

    # Calcula o peso esperado total
    carrinho = carrinhos_itens.get(id, {})

    if produto.acao == 'adicionar':
        carrinho_copy = carrinhos_itens[id].copy()
        carrinho_copy[produto.nome] = carrinho_copy.get(produto.nome, 0) + produto.quantidade
        peso_esperado = sum(produtos[nome] * qtd for nome, qtd in carrinho_copy.items())

    elif produto.acao == 'remover':
        carrinho_copy = carrinhos_itens[id].copy()
        if carrinho_copy.get(produto.nome, 0) > 0:
            carrinho_copy[produto.nome] -= produto.quantidade
            if carrinho_copy[produto.nome] <= 0:
                del carrinho_copy[produto.nome]
        peso_esperado = sum(produtos[nome] * qtd for nome, qtd in carrinho_copy.items())

    margem = max(0.07, peso_esperado * 0.10)

    # Aguarda leitura do ESP32
    for _ in range(20):
        await asyncio.sleep(0.5)
        peso_lido = pesos_atuais.get(id)
        if peso_lido is not None:
            diferenca = round(peso_lido - peso_esperado, 3)
            print(f"Esperado: {peso_esperado}, Lido: {peso_lido}, Diferença: {diferenca}")

            if abs(peso_lido - peso_esperado) <= margem:
                # Só aqui atualiza o carrinho!
                carrinhos_itens[id] = carrinho_copy 
                return {
                    "status": "confirmado",
                    "peso_lido": peso_lido,
                    "diferenca": diferenca
                }

            return {
                "status": "erro",
                "mensagem": f"Peso incompatível para ação '{produto.acao}'",
                "peso_lido": peso_lido,
                "diferenca": diferenca,
                "esperado": peso_esperado,
                "margem": margem
            }

    return {"status": "erro", "mensagem": "Sem leitura de peso"}
