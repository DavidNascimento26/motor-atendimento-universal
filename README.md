# Motor de Atendimento Universal

Sistema de atendimento automático via WhatsApp para negócios locais (barbearias, salões, pet shops e outros), powered by **FastAPI** + **Groq AI** (LLaMA 3).

Cada negócio tem seu próprio perfil em JSON — sem código, sem complicação. O sistema lê o perfil, monta um prompt inteligente e responde aos clientes automaticamente com a personalidade e informações do negócio.

---

## Instalação

```bash
pip install -r requirements.txt
```

---

## Configuração das variáveis de ambiente

Copie o arquivo de exemplo e preencha com suas chaves:

```bash
cp .env.example .env
```

Edite o `.env`:

```env
GROQ_API_KEY=sua_chave_groq_aqui
VERIFY_TOKEN=motor123
```

- **GROQ_API_KEY**: Obtenha gratuitamente em [console.groq.com](https://console.groq.com)
- **VERIFY_TOKEN**: Token de verificação do webhook Meta (pode manter `motor123` ou trocar por qualquer string)

---

## Como rodar

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Acesse `http://localhost:8000` para confirmar que está no ar.

---

## Como adicionar um novo cliente

1. Crie um arquivo `.json` dentro da pasta `clientes/`. O nome do arquivo será o ID do cliente.

   Exemplo: `clientes/minha_pizzaria.json`

2. Use a estrutura abaixo como base:

```json
{
  "nome_negocio": "Pizzaria do Zé",
  "artigo": "a",
  "tipo": "pizzaria",
  "servicos": [
    {"nome": "Pizza Margherita", "preco": "R$45"},
    {"nome": "Pizza Calabresa", "preco": "R$50"}
  ],
  "horarios": "Terça a Domingo, das 18h às 23h",
  "endereco": "Rua da Pizza, 10 - Centro",
  "agendamento": "Peça pelo WhatsApp: (11) 91234-5678",
  "tom": "animado e acolhedor",
  "saudacao": "Olá! Bem-vindo à Pizzaria do Zé 🍕",
  "pagamentos": "Pix, dinheiro e cartão",
  "obs_extras": "Entregamos em até 40 minutos"
}
```

3. Pronto! O novo cliente já estará disponível em `/webhook/minha_pizzaria` e `/testar/minha_pizzaria`.

---

## Testando pelo navegador (rota /testar)

Você pode testar qualquer cliente sem precisar do WhatsApp usando a rota `POST /testar/{cliente_id}`.

### Com curl:

```bash
# Testar a Barbearia
curl -X POST http://localhost:8000/testar/exemplo_barbearia \
  -H "Content-Type: application/json" \
  -d '{"mensagem": "Qual o preço do corte?"}'

# Testar o Salão
curl -X POST http://localhost:8000/testar/exemplo_salao \
  -H "Content-Type: application/json" \
  -d '{"mensagem": "Quais serviços vocês oferecem?"}'

# Testar o Pet Shop
curl -X POST http://localhost:8000/testar/exemplo_petshop \
  -H "Content-Type: application/json" \
  -d '{"mensagem": "Quanto custa o banho de cachorro grande?"}'
```

### Com a documentação interativa (Swagger):

Acesse `http://localhost:8000/docs` no navegador — você pode testar todas as rotas diretamente pela interface.

---

## URLs disponíveis por cliente

| Cliente          | Webhook (WhatsApp)                   | Teste direto                         |
|------------------|--------------------------------------|--------------------------------------|
| Barbearia do João | `POST /webhook/exemplo_barbearia`   | `POST /testar/exemplo_barbearia`    |
| Salão da Maria   | `POST /webhook/exemplo_salao`        | `POST /testar/exemplo_salao`        |
| Pet Shop Rex     | `POST /webhook/exemplo_petshop`      | `POST /testar/exemplo_petshop`      |

---

## Integração com WhatsApp

### Opção 1 — Meta WhatsApp Cloud API (oficial)
Configure o webhook no painel Meta com a URL:
```
https://SEU_DOMINIO/webhook/{cliente_id}
```
O token de verificação é o valor de `VERIFY_TOKEN` no `.env`.

### Opção 2 — Z-API ou Evolution API
Configure o webhook de mensagens recebidas para:
```
https://SEU_DOMINIO/webhook/{cliente_id}
```
O sistema detecta automaticamente os dois formatos (Meta e Z-API).

---

## Estrutura de arquivos

```
motor-atendimento/
├── main.py                      # Aplicação principal FastAPI
├── requirements.txt             # Dependências Python
├── .env.example                 # Exemplo de variáveis de ambiente
├── clientes/
│   ├── exemplo_barbearia.json   # Perfil: Barbearia do João
│   ├── exemplo_salao.json       # Perfil: Salão da Maria
│   └── exemplo_petshop.json     # Perfil: Pet Shop Rex
└── README.md
```
