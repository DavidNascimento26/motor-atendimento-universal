import requests
import json

BASE_URL = "http://localhost:8000"

testes = [
    {
        "cliente_id": "exemplo_barbearia",
        "mensagem": "Qual o preço do corte?"
    },
    {
        "cliente_id": "exemplo_barbearia",
        "mensagem": "Tem horário sábado?"
    },
    {
        "cliente_id": "dra_juliana",
        "mensagem": "Quanto custa a consulta?"
    },
    {
        "cliente_id": "dra_juliana",
        "mensagem": "Estou me sentindo muito mal"
    },
]

print("=" * 60)
print("  MOTOR DE ATENDIMENTO UNIVERSAL — TESTE DE RESPOSTAS")
print("=" * 60)

for i, teste in enumerate(testes, 1):
    url = f"{BASE_URL}/testar/{teste['cliente_id']}"
    payload = {"mensagem": teste["mensagem"]}

    print(f"\n[Teste {i}]")
    print(f"  Cliente  : {teste['cliente_id']}")
    print(f"  Mensagem : {teste['mensagem']}")

    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            print(f"  Cliente  : {data.get('cliente', '—')}")
            print(f"  Resposta : {data.get('resposta_bot', '—')}")
        else:
            print(f"  ERRO {response.status_code}: {response.text}")
    except requests.exceptions.ConnectionError:
        print("  ERRO: Servidor não está rodando em localhost:8000")
    except requests.exceptions.Timeout:
        print("  ERRO: Timeout — o servidor demorou mais de 30s para responder")
    except Exception as e:
        print(f"  ERRO inesperado: {e}")

    print("-" * 60)

print("\nTeste concluído!")
