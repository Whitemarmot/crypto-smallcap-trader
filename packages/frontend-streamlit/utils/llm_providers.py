"""
🤖 Multi-LLM Provider - Support Claude, Gemini, Grok, OpenAI
Avec logging des prompts/réponses
"""

import os
import json
import requests
from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

load_dotenv()

# API Keys from environment
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')  # Gemini
XAI_API_KEY = os.getenv('XAI_API_KEY')  # Grok
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')  # All models in one!

# OpenClaw (Jean-Michel) - local gateway
OPENCLAW_TOKEN = os.getenv('OPENCLAW_TOKEN', '354943dd82e0b4e2860dd25a7fcebdfcfc2b079c2a5bf34e')
OPENCLAW_URL = os.getenv('OPENCLAW_URL', 'http://localhost:18789')

# Log file path
LOG_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'llm_logs.json')


@dataclass
class LLMLog:
    """Log entry for LLM call"""
    timestamp: str
    provider: str
    model: str
    prompt: str
    response: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    error: Optional[str] = None
    

# Available models per provider
LLM_MODELS = {
    'openclaw': {
        'name': '🥖 Jean-Michel (OpenClaw)',
        'icon': '🥖',
        'models': {
            'openclaw:main': 'Jean-Michel (Claude Opus)',
        },
        'default': 'openclaw:main',
        'api_key_env': 'OPENCLAW_TOKEN',
        'always_available': True  # Local, no external API needed
    },
    'openrouter': {
        'name': 'OpenRouter (tous modèles)',
        'icon': '🌐',
        'models': {
            # Claude
            'anthropic/claude-3-haiku': 'Claude 3 Haiku (rapide)',
            'anthropic/claude-3.5-sonnet': 'Claude 3.5 Sonnet',
            'anthropic/claude-3-opus': 'Claude 3 Opus',
            # GPT
            'openai/gpt-4o-mini': 'GPT-4o Mini',
            'openai/gpt-4o': 'GPT-4o',
            'openai/gpt-4-turbo': 'GPT-4 Turbo',
            # Gemini
            'google/gemini-flash-1.5': 'Gemini 1.5 Flash',
            'google/gemini-pro-1.5': 'Gemini 1.5 Pro',
            # Grok
            'x-ai/grok-beta': 'Grok Beta',
            # Llama
            'meta-llama/llama-3.1-70b-instruct': 'Llama 3.1 70B',
            'meta-llama/llama-3.1-8b-instruct': 'Llama 3.1 8B (gratuit)',
            # Mistral
            'mistralai/mistral-large': 'Mistral Large',
            'mistralai/mistral-7b-instruct': 'Mistral 7B (gratuit)',
            # DeepSeek
            'deepseek/deepseek-chat': 'DeepSeek Chat',
            # Qwen
            'qwen/qwen-2.5-72b-instruct': 'Qwen 2.5 72B',
        },
        'default': 'anthropic/claude-3-haiku',
        'api_key_env': 'OPENROUTER_API_KEY'
    },
    'anthropic': {
        'name': 'Claude (Anthropic)',
        'icon': '🟣',
        'models': {
            'claude-3-haiku-20240307': 'Claude 3 Haiku (rapide)',
            'claude-3-5-sonnet-20241022': 'Claude 3.5 Sonnet',
            'claude-sonnet-4-20250514': 'Claude Sonnet 4',
        },
        'default': 'claude-3-haiku-20240307',
        'api_key_env': 'ANTHROPIC_API_KEY'
    },
    'google': {
        'name': 'Gemini (Google)',
        'icon': '🔵',
        'models': {
            'gemini-1.5-flash': 'Gemini 1.5 Flash (rapide)',
            'gemini-1.5-pro': 'Gemini 1.5 Pro',
            'gemini-2.0-flash': 'Gemini 2.0 Flash',
        },
        'default': 'gemini-1.5-flash',
        'api_key_env': 'GOOGLE_API_KEY'
    },
    'xai': {
        'name': 'Grok (xAI)',
        'icon': '⚫',
        'models': {
            'grok-beta': 'Grok Beta',
            'grok-2': 'Grok 2',
        },
        'default': 'grok-beta',
        'api_key_env': 'XAI_API_KEY'
    },
    'openai': {
        'name': 'OpenAI',
        'icon': '🟢',
        'models': {
            'gpt-4o-mini': 'GPT-4o Mini (rapide)',
            'gpt-4o': 'GPT-4o',
            'gpt-4-turbo': 'GPT-4 Turbo',
        },
        'default': 'gpt-4o-mini',
        'api_key_env': 'OPENAI_API_KEY'
    }
}


def get_available_providers() -> Dict[str, Any]:
    """Get providers that have API keys configured"""
    available = {}
    
    # OpenClaw (Jean-Michel) first - always available locally!
    if OPENCLAW_TOKEN:
        available['openclaw'] = LLM_MODELS['openclaw']
    
    # OpenRouter (recommended - all models in one)
    if OPENROUTER_API_KEY:
        available['openrouter'] = LLM_MODELS['openrouter']
    if ANTHROPIC_API_KEY:
        available['anthropic'] = LLM_MODELS['anthropic']
    if GOOGLE_API_KEY:
        available['google'] = LLM_MODELS['google']
    if XAI_API_KEY:
        available['xai'] = LLM_MODELS['xai']
    if OPENAI_API_KEY:
        available['openai'] = LLM_MODELS['openai']
    
    return available


def log_llm_call(log: LLMLog):
    """Save LLM call to log file"""
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    
    logs = []
    if os.path.exists(LOG_PATH):
        try:
            with open(LOG_PATH, 'r') as f:
                logs = json.load(f)
        except:
            logs = []
    
    logs.append(asdict(log))
    
    # Keep last 100 logs
    logs = logs[-100:]
    
    with open(LOG_PATH, 'w') as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)


def get_llm_logs(limit: int = 50) -> list:
    """Get recent LLM logs"""
    if not os.path.exists(LOG_PATH):
        return []
    
    try:
        with open(LOG_PATH, 'r') as f:
            logs = json.load(f)
        return logs[-limit:][::-1]  # Most recent first
    except:
        return []


def call_anthropic(prompt: str, model: str = 'claude-3-haiku-20240307') -> tuple:
    """Call Anthropic Claude API"""
    import time
    start = time.time()
    
    try:
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'Content-Type': 'application/json',
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01'
            },
            json={
                'model': model,
                'max_tokens': 1000,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=60
        )
        
        latency = int((time.time() - start) * 1000)
        
        if response.status_code == 200:
            data = response.json()
            text = data.get('content', [{}])[0].get('text', '')
            usage = data.get('usage', {})
            return text, usage.get('input_tokens', 0), usage.get('output_tokens', 0), latency, None
        else:
            return None, 0, 0, latency, f"Error {response.status_code}: {response.text}"
            
    except Exception as e:
        return None, 0, 0, int((time.time() - start) * 1000), str(e)


def call_google(prompt: str, model: str = 'gemini-1.5-flash') -> tuple:
    """Call Google Gemini API"""
    import time
    start = time.time()
    
    try:
        response = requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
            params={'key': GOOGLE_API_KEY},
            headers={'Content-Type': 'application/json'},
            json={
                'contents': [{'parts': [{'text': prompt}]}],
                'generationConfig': {'maxOutputTokens': 1000}
            },
            timeout=60
        )
        
        latency = int((time.time() - start) * 1000)
        
        if response.status_code == 200:
            data = response.json()
            text = data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
            usage = data.get('usageMetadata', {})
            return text, usage.get('promptTokenCount', 0), usage.get('candidatesTokenCount', 0), latency, None
        else:
            return None, 0, 0, latency, f"Error {response.status_code}: {response.text}"
            
    except Exception as e:
        return None, 0, 0, int((time.time() - start) * 1000), str(e)


def call_xai(prompt: str, model: str = 'grok-beta') -> tuple:
    """Call xAI Grok API"""
    import time
    start = time.time()
    
    try:
        response = requests.post(
            'https://api.x.ai/v1/chat/completions',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {XAI_API_KEY}'
            },
            json={
                'model': model,
                'max_tokens': 1000,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=60
        )
        
        latency = int((time.time() - start) * 1000)
        
        if response.status_code == 200:
            data = response.json()
            text = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            usage = data.get('usage', {})
            return text, usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0), latency, None
        else:
            return None, 0, 0, latency, f"Error {response.status_code}: {response.text}"
            
    except Exception as e:
        return None, 0, 0, int((time.time() - start) * 1000), str(e)


def call_openai(prompt: str, model: str = 'gpt-4o-mini') -> tuple:
    """Call OpenAI API"""
    import time
    start = time.time()
    
    try:
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {OPENAI_API_KEY}'
            },
            json={
                'model': model,
                'max_tokens': 1000,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=60
        )
        
        latency = int((time.time() - start) * 1000)
        
        if response.status_code == 200:
            data = response.json()
            text = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            usage = data.get('usage', {})
            return text, usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0), latency, None
        else:
            return None, 0, 0, latency, f"Error {response.status_code}: {response.text}"
            
    except Exception as e:
        return None, 0, 0, int((time.time() - start) * 1000), str(e)


def call_openrouter(prompt: str, model: str = 'anthropic/claude-3-haiku') -> tuple:
    """Call OpenRouter API - Access all models with one key!"""
    import time
    start = time.time()
    
    try:
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                'HTTP-Referer': 'https://trader.lecoineur.com',
                'X-Title': 'Crypto SmallCap Trader'
            },
            json={
                'model': model,
                'max_tokens': 1000,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=60
        )
        
        latency = int((time.time() - start) * 1000)
        
        if response.status_code == 200:
            data = response.json()
            text = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            usage = data.get('usage', {})
            return text, usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0), latency, None
        else:
            return None, 0, 0, latency, f"Error {response.status_code}: {response.text}"
            
    except Exception as e:
        return None, 0, 0, int((time.time() - start) * 1000), str(e)


def call_openclaw(prompt: str, model: str = 'openclaw:main', thinking: str = 'high') -> tuple:
    """
    Call OpenClaw (Jean-Michel) API - Local gateway with extended thinking!
    thinking: 'off', 'low', 'medium', 'high' (high = more reasoning tokens)
    """
    import time
    start = time.time()
    
    try:
        # Build request with thinking mode
        request_body = {
            'model': model,
            'messages': [{'role': 'user', 'content': prompt}]
        }
        
        # Add thinking parameter if not 'off'
        if thinking and thinking != 'off':
            request_body['thinking'] = thinking
        
        response = requests.post(
            f'{OPENCLAW_URL}/v1/chat/completions',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {OPENCLAW_TOKEN}'
            },
            json=request_body,
            timeout=180  # Longer timeout for thinking mode
        )
        
        latency = int((time.time() - start) * 1000)
        
        if response.status_code == 200:
            data = response.json()
            choice = data.get('choices', [{}])[0]
            message = choice.get('message', {})
            text = message.get('content', '')
            
            # Extract thinking if present
            thinking_content = message.get('thinking', '')
            if thinking_content:
                print(f"[THINKING] {thinking_content[:500]}...")
            
            usage = data.get('usage', {})
            return text, usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0), latency, None
        else:
            return None, 0, 0, latency, f"Error {response.status_code}: {response.text}"
            
    except Exception as e:
        return None, 0, 0, int((time.time() - start) * 1000), str(e)


def call_llm(prompt: str, provider: str, model: str, thinking: str = 'high') -> str:
    """
    Universal LLM caller with logging
    thinking: 'off', 'low', 'medium', 'high' (for providers that support it)
    Returns the response text
    """
    # Call the appropriate provider
    if provider == 'openclaw':
        text, tokens_in, tokens_out, latency, error = call_openclaw(prompt, model, thinking=thinking)
    elif provider == 'openrouter':
        text, tokens_in, tokens_out, latency, error = call_openrouter(prompt, model)
    elif provider == 'anthropic':
        text, tokens_in, tokens_out, latency, error = call_anthropic(prompt, model)
    elif provider == 'google':
        text, tokens_in, tokens_out, latency, error = call_google(prompt, model)
    elif provider == 'xai':
        text, tokens_in, tokens_out, latency, error = call_xai(prompt, model)
    elif provider == 'openai':
        text, tokens_in, tokens_out, latency, error = call_openai(prompt, model)
    else:
        return None
    
    # Log the call
    log = LLMLog(
        timestamp=datetime.now().isoformat(),
        provider=provider,
        model=model,
        prompt=prompt[:2000],  # Truncate for storage
        response=text[:2000] if text else '',
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=latency,
        error=error
    )
    log_llm_call(log)
    
    return text
