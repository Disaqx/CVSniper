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
use_AI = False      # True o False / True or False
'''
Set True if you want to use AI features.
Options:
  - Local LLM (Ollama, LM Studio, llama.cpp, Jan)
  - OpenAI API key
  - Gemini API key
  - DeepSeek API key
'''

# Proveedor de IA / AI Provider
ai_provider = "gemini"   # "openai", "deepseek", "gemini"

# URL de la API del LLM (no necesario para Gemini)
# LLM API URL (not needed for Gemini)
llm_api_url = "https://api.openai.com/v1/"

# Tu API Key / Your API Key
llm_api_key = "YOUR_API_KEY_HERE"
'''
Note: Leave as "" or "not-needed" if using a local LLM without auth.
'''

# Nombre del modelo / Model name
llm_model = "gemini-2.5-flash"
'''
Examples:
  OpenAI:  "gpt-4o", "gpt-4o-mini"
  Gemini:  "gemini-2.5-flash", "gemini-2.0-flash"
  DeepSeek: "deepseek-chat"
  Local:   "llama-3.2-3b-instruct", "qwen3:latest"
'''

llm_spec = "openai"   # "openai", "openai-like", "gemini"

# Mostrar alertas de error de IA / Show AI error alerts
showAiErrorAlerts = True

# Transmitir salida de IA / Stream AI output
stream_output = False
