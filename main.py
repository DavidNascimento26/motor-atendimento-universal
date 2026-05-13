from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from groq import Groq
import os, json, logging, requests
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
            raise HTTPException(status_code=503, detail="GROQ_API_KEY não configurada.")
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

def extrair_mensagem_meta(data: dict) -> tuple[str | None, str | None, str | None]:
    """Extrai mensagem, número e phone_number_id do formato Meta/WhatsApp Cloud API"""
    try:
        value = data["entry"][0]["changes"][0]["value"]
        messages = value.get("messages", [])
        if not messages:
            return None, None, None
        msg = messages[0]
        texto = msg.get("text", {}).get("body")
        numero = msg.get("from")
        phone_number_id = value.get("metadata", {}).get("phone_number_id")
        return texto, numero, phone_number_id
    except (KeyError, IndexError):
        return None, None, None

def extrair_mensagem_zapi(data: dict) -> tuple[str | None, str | None, str | None]:
    """Extrai mensagem e número do formato Z-API (sem phone_number_id)"""
    try:
        texto = data.get("text", {}).get("message") or data.get("body")
        numero = data.get("phone") or data.get("from")
        if data.get("fromMe"):
            return None, None, None
        return texto, numero, None
    except Exception:
        return None, None, None

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

def enviar_mensagem_whatsapp(numero: str, texto: str, phone_number_id: str) -> bool:
    """Envia mensagem de texto via Meta WhatsApp Cloud API"""
    token = os.environ.get("WHATSAPP_TOKEN")
    if not token:
        logger.warning("WHATSAPP_TOKEN não configurado — resposta gerada mas não enviada ao WhatsApp.")
        return False

    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"body": texto}
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code == 200:
            logger.info(f"Mensagem enviada para {numero}")
            return True
        else:
            logger.error(f"Erro ao enviar mensagem: {resp.status_code} — {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Exceção ao enviar mensagem WhatsApp: {e}")
        return False

# ========== ROTAS ==========

@app.get("/")
def status():
    token_ok    = bool(os.environ.get("WHATSAPP_TOKEN"))
    groq_ok     = bool(os.environ.get("GROQ_API_KEY"))
    return {
        "status": "Motor de Atendimento Universal Online",
        "versao": "1.0.0",
        "groq_configurado": groq_ok,
        "whatsapp_configurado": token_ok,
        "uso": "POST /webhook/{cliente_id} para receber mensagens do WhatsApp"
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
    """Recebe mensagem do WhatsApp, gera resposta com IA e envia de volta"""

    cfg = carregar_cliente(cliente_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Cliente '{cliente_id}' não encontrado")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON inválido")

    logger.info(f"Payload recebido para {cliente_id}: {json.dumps(data)[:300]}")

    # Tenta extrair nos dois formatos — Meta tem priority por retornar phone_number_id
    texto, numero, phone_number_id = extrair_mensagem_meta(data)
    formato = "meta"
    if not texto:
        texto, numero, phone_number_id = extrair_mensagem_zapi(data)
        formato = "zapi"

    if not texto:
        return {"status": "ok", "info": "Nenhuma mensagem de texto encontrada"}

    logger.info(f"[{cliente_id}] [{formato}] De {numero}: {texto}")

    system_prompt = montar_system_prompt(cfg)
    resposta = gerar_resposta_ia(system_prompt, texto)
    logger.info(f"[{cliente_id}] Resposta gerada: {resposta}")

    # Envia de volta ao WhatsApp (apenas se vier da Meta e tiver phone_number_id)
    enviado = False
    if formato == "meta" and phone_number_id:
        enviado = enviar_mensagem_whatsapp(numero, resposta, phone_number_id)
    elif not phone_number_id:
        # Tenta usar o phone_number_id padrão configurado como variável de ambiente
        phone_id_env = os.environ.get("WHATSAPP_PHONE_ID")
        if phone_id_env and numero:
            enviado = enviar_mensagem_whatsapp(numero, resposta, phone_id_env)

    return {
        "status": "ok",
        "cliente": cfg["nome_negocio"],
        "de": numero,
        "mensagem_recebida": texto,
        "resposta_gerada": resposta,
        "enviado_whatsapp": enviado
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
