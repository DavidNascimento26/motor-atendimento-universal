from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from groq import Groq
import os, json, logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Motor de Atendimento Universal", version="1.0.0")

_groq_client = None

def get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise HTTPException(status_code=503, detail="GROQ_API_KEY não configurada. Adicione o Secret no Replit.")
        _groq_client = Groq(api_key=api_key)
    return _groq_client

def carregar_cliente(cliente_id: str) -> dict | None:
    caminho = f"clientes/{cliente_id}.json"
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Cliente não encontrado: {cliente_id}")
        return None
    except json.JSONDecodeError:
        logger.error(f"JSON inválido para cliente: {cliente_id}")
        return None

def montar_system_prompt(cfg: dict) -> str:
    servicos_formatados = "\n".join([
        f"  • {s['nome']}: {s['preco']}"
        for s in cfg.get("servicos", [])
    ])

    prompt = f"""Você é a assistente virtual d{cfg.get('artigo', 'o')} {cfg['nome_negocio']}.

PERSONALIDADE: {cfg.get('tom', 'simpático e profissional')}
SAUDAÇÃO PADRÃO: {cfg.get('saudacao', 'Olá! Como posso ajudar?')}

SERVIÇOS E PREÇOS:
{servicos_formatados}

HORÁRIOS DE FUNCIONAMENTO: {cfg['horarios']}
ENDEREÇO: {cfg.get('endereco', 'Consulte pelo WhatsApp')}
COMO AGENDAR: {cfg['agendamento']}
FORMAS DE PAGAMENTO: {cfg.get('pagamentos', 'Consulte conosco')}
OBSERVAÇÕES: {cfg.get('obs_extras', 'Nenhuma')}

REGRAS IMPORTANTES:
1. Seja breve e direto — máximo 4 linhas por resposta
2. Nunca invente preços, horários ou serviços que não estão listados acima
3. Se perguntarem algo que você não sabe, diga: "Vou chamar o responsável para te ajudar com isso!"
4. Use emojis com moderação (1 a 2 por mensagem)
5. Se o cliente quiser agendar, oriente-o conforme as instruções de agendamento
6. Seja sempre gentil mesmo com clientes impacientes
7. Responda sempre em português brasileiro"""

    if cfg.get("tipo") == "psicologa":
        prompt += """

REGRAS ESPECIAIS PARA CONSULTÓRIO DE PSICOLOGIA:
- Você NUNCA deve dar conselhos psicológicos, emocionais ou terapêuticos
- Você NUNCA deve tentar interpretar sentimentos do usuário
- Sua função é APENAS informar sobre agendamento, valores e horários
- Se o usuário demonstrar sofrimento, crise, tristeza profunda ou mencionar algo preocupante, responda SEMPRE assim:
  "Entendo que você está passando por um momento difícil. A Dra. Juliana pode te ajudar com isso. Vou avisar ela para entrar em contato com você o mais breve possível 💙"
- Nunca tente substituir o papel da psicóloga"""

    return prompt

def extrair_mensagem_meta(data: dict) -> tuple[str | None, str | None]:
    """Extrai mensagem e número do formato Meta/WhatsApp Cloud API"""
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        messages = entry.get("messages", [])
        if not messages:
            return None, None
        msg = messages[0]
        texto = msg.get("text", {}).get("body")
        numero = msg.get("from")
        return texto, numero
    except (KeyError, IndexError):
        return None, None

def extrair_mensagem_zapi(data: dict) -> tuple[str | None, str | None]:
    """Extrai mensagem e número do formato Z-API"""
    try:
        texto = data.get("text", {}).get("message") or data.get("body")
        numero = data.get("phone") or data.get("from")
        if data.get("fromMe"):
            return None, None
        return texto, numero
    except Exception:
        return None, None

def gerar_resposta_ia(system_prompt: str, mensagem_usuario: str) -> str:
    try:
        response = get_groq_client().chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": mensagem_usuario}
            ],
            max_tokens=300,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Erro na API Groq: {e}")
        return "Desculpe, tive um problema técnico. Por favor, tente novamente em instantes!"

# ========== ROTAS ==========

@app.get("/")
def status():
    return {
        "status": "Motor de Atendimento Universal Online",
        "versao": "1.0.0",
        "uso": "POST /webhook/{cliente_id} para receber mensagens"
    }

@app.get("/clientes")
def listar_clientes():
    """Lista todos os clientes configurados"""
    try:
        arquivos = os.listdir("clientes")
        clientes = [f.replace(".json", "") for f in arquivos if f.endswith(".json")]
        return {"clientes_ativos": clientes, "total": len(clientes)}
    except Exception:
        return {"clientes_ativos": [], "total": 0}

@app.get("/webhook/{cliente_id}")
def verificar_webhook(
    cliente_id: str,
    hub_mode: str = None,
    hub_challenge: str = None,
    hub_verify_token: str = None
):
    """Verificação de webhook — necessário para Meta WhatsApp API"""
    verify_token = os.environ.get("VERIFY_TOKEN", "motor123")
    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        logger.info(f"Webhook verificado para cliente: {cliente_id}")
        return PlainTextResponse(content=hub_challenge)
    raise HTTPException(status_code=403, detail="Token de verificação inválido")

@app.post("/webhook/{cliente_id}")
async def receber_mensagem(cliente_id: str, request: Request):
    """Recebe mensagem do WhatsApp e responde com IA"""

    cfg = carregar_cliente(cliente_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Cliente '{cliente_id}' não encontrado")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON inválido")

    logger.info(f"Mensagem recebida para {cliente_id}: {json.dumps(data)[:200]}")

    # Tenta extrair mensagem nos dois formatos (Meta e Z-API)
    texto, numero = extrair_mensagem_meta(data)
    if not texto:
        texto, numero = extrair_mensagem_zapi(data)

    if not texto:
        return {"status": "ok", "info": "Nenhuma mensagem de texto encontrada"}

    logger.info(f"[{cliente_id}] De {numero}: {texto}")

    system_prompt = montar_system_prompt(cfg)
    resposta = gerar_resposta_ia(system_prompt, texto)

    logger.info(f"[{cliente_id}] Resposta: {resposta}")

    return {
        "status": "ok",
        "cliente": cfg["nome_negocio"],
        "de": numero,
        "mensagem_recebida": texto,
        "resposta_gerada": resposta
    }

@app.post("/testar/{cliente_id}")
async def testar_bot(cliente_id: str, request: Request):
    """Rota de teste — envia mensagem e vê a resposta sem precisar do WhatsApp"""
    cfg = carregar_cliente(cliente_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    body = await request.json()
    mensagem = body.get("mensagem", "Olá, quais são os serviços?")

    system_prompt = montar_system_prompt(cfg)
    resposta = gerar_resposta_ia(system_prompt, mensagem)

    return {
        "cliente": cfg["nome_negocio"],
        "sua_mensagem": mensagem,
        "resposta_bot": resposta
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=True)
