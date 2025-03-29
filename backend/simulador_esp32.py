import asyncio
import websockets
import json

async def simular_envio_peso(carrinho_id: str):
    uri = f"ws://localhost:8000/carrinho/{carrinho_id}"
    try:
        async with websockets.connect(uri) as websocket:
            print(f"✅ Conectado como carrinho {carrinho_id}")

            while True:
                peso = float(input("Digite o peso simulado (kg): "))
                mensagem = json.dumps({"peso": peso})
                await websocket.send(mensagem)
                print(f"📤 Peso enviado: {mensagem}")
    except Exception as e:
        print(f"❌ Erro na conexão: {e}")

asyncio.run(simular_envio_peso("123"))
