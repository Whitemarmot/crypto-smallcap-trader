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


def call_llm(prompt: str, provider: str, model: str) -> str:
    """
    Universal LLM caller with logging
    Returns the response text
    """
    # Call the appropriate provider
    if provider == 'anthropic':
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
