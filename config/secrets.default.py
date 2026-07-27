'''
CVSniper - Template de Credenciales / Credentials Template

Rellena tus datos aqui / Fill in your data here.
Este archivo es tuyo - NUNCA se sube al repositorio.
This file is yours - it is NEVER uploaded to the repository.
'''

# Credenciales de LinkedIn (Opcional - el bot puede usar tu sesion de Chrome abierta)
# LinkedIn credentials (Optional - bot can use your already open Chrome session)
username = ""       # Tu email de LinkedIn / Your LinkedIn email
password = ""       # Tu contrasena / Your password


## Inteligencia Artificial / Artificial Intelligence
use_AI = True       # True o False / True or False
'''
Manten esto en True para que el bot responda preguntas de los formularios con IA.
Keep this True so the bot answers form questions using AI.
'''

# Proveedor de IA / AI Provider
ai_provider = "groq"   # "openai", "deepseek", "gemini", "groq"
'''
Opciones / Options:
  "groq"     → GRATIS. Crea cuenta en https://console.groq.com → API Keys → Create key.
               Pega la key en llm_api_key. Es la opcion recomendada para empezar.
               FREE. Create account at https://console.groq.com → API Keys → Create key.
  "gemini"   → Google Gemini. Gratis con limites. https://aistudio.google.com/apikey
  "openai"   → OpenAI (GPT) o cualquier API compatible con OpenAI (Ollama, LM Studio).
  "deepseek" → DeepSeek. Muy barato.
'''

# URL de la API del LLM (solo para openai / only for openai provider)
# LLM API URL (not needed for Gemini or Groq)
llm_api_url = "https://api.groq.com/openai/v1"
'''
Ejemplos / Examples:
  Groq:    "https://api.groq.com/openai/v1"
  OpenAI:  "https://api.openai.com/v1/"
  Ollama:  "http://localhost:11434/v1"
  DeepSeek: "https://api.deepseek.com"
'''

# Tu API Key / Your API Key
llm_api_key = "YOUR_GROQ_API_KEY_HERE"
'''
Groq:    Gratis en https://console.groq.com → API Keys → Create key
OpenAI:  De pago en https://platform.openai.com/api-keys
Gemini:  Gratis en https://aistudio.google.com/apikey
DeepSeek: Muy barato en https://platform.deepseek.com/api_keys
Ollama local: poner "not-needed"
'''

# Nombre del modelo / Model name
llm_model = "llama-3.1-8b-instant"
'''
Groq (gratis / free):
  "llama-3.1-8b-instant"    → rapido, respuestas en <1s (recomendado / recommended)
  "llama-3.3-70b-versatile" → mejor calidad, mas lento
  "gemma2-9b-it"            → alternativa
Gemini (gratis con limites):
  "gemini-2.5-flash", "gemini-2.0-flash"
OpenAI (de pago):
  "gpt-4o-mini", "gpt-4o"
DeepSeek:
  "deepseek-chat"
Ollama local:
  "llama3.2", "phi3.5", "mistral"
'''

llm_spec = "openai-like"   # "openai", "openai-like", "gemini"
'''
Groq / Ollama / DeepSeek / APIs compatibles: usar "openai-like"
OpenAI oficial: usar "openai"
Gemini: no importa, se ignora
'''

# Mostrar alertas de error de IA / Show AI error alerts
showAiErrorAlerts = True

# Transmitir salida de IA / Stream AI output
stream_output = False
