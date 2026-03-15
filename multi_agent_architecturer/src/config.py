"""
Configuration module for UMI 16S rRNA Multi-Agent Pipeline
Loads API keys from .env and agent config from agents.yaml
"""

import os
from pathlib import Path
from typing import Dict, Optional

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # Fallback: try llm_genetics_assistant .env
        fallback_env = Path(__file__).parent.parent / "llm_genetics_assistant" / ".env"
        if fallback_env.exists():
            load_dotenv(fallback_env)
except ImportError:
    pass

try:
    import yaml
except ImportError:
    yaml = None


def load_agents_config() -> Dict:
    config_path = Path(__file__).parent.parent / "config" / "agents.yaml"
    if yaml is None:
        raise ImportError("PyYAML is required. Install with: pip install pyyaml")
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_api_key(env_var: str) -> str:
    key = os.getenv(env_var)
    if not key:
        raise ValueError(
            f"{env_var} not found in environment variables.\n"
            f"Set it in .env or export {env_var}='your-key-here'"
        )
    return key


def get_llm_config(agent_config: Dict) -> Dict:
    """Resolve LLM config for an agent, falling back to defaults."""
    agents_config = load_agents_config()
    defaults = agents_config.get("llm_defaults", {})
    agent_llm = agent_config.get("llm", {})
    return {
        "provider": agent_llm.get("provider", defaults.get("provider", "xai")),
        "model": agent_llm.get("model", defaults.get("model", "grok-3-mini-fast")),
        "temperature": agent_llm.get("temperature", defaults.get("temperature", 0.3)),
        "max_tokens": agent_llm.get("max_tokens", defaults.get("max_tokens", 4000)),
    }


# Provider-specific API call functions
def call_llm(prompt: str, system_msg: str, llm_config: Dict) -> str:
    """Unified LLM call that dispatches to the correct provider."""
    import requests
    import json
    provider = llm_config["provider"]

    if provider == "xai":
        api_key = get_api_key("GROK_API_KEY")
        url = "https://api.x.ai/v1/chat/completions"
        model = llm_config["model"]
    elif provider == "deepseek":
        api_key = get_api_key("DEEPSEEK_API_KEY")
        url = "https://api.deepseek.com/chat/completions"
        model = llm_config.get("model", "deepseek-chat")
    elif provider == "openai":
        api_key = get_api_key("OPENAI_API_KEY")
        url = "https://api.openai.com/v1/chat/completions"
        model = llm_config.get("model", "gpt-4o")
    elif provider == "google":
        # For Google Gemini via OpenAI-compatible endpoint
        api_key = get_api_key("GOOGLE_API_KEY")
        url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        model = llm_config.get("model", "gemini-2.5-flash")
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt},
    ]

    data = {
        "model": model,
        "messages": messages,
        "temperature": llm_config.get("temperature", 0.3),
        "max_tokens": llm_config.get("max_tokens", 4000),
    }

    # Add tools for Grok web search
    if provider == "xai":
        data["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Perform a web search",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "The search query"}
                        },
                        "required": ["query"]
                    }
                }
            }
        ]

    # First request
    resp = requests.post(url, headers=headers, json=data, timeout=120)
    resp.raise_for_status()
    response_data = resp.json()
    message = response_data["choices"][0]["message"]

    # Handle tool calls
    while "tool_calls" in message and message["tool_calls"]:
        tool_call = message["tool_calls"][0]
        function_name = tool_call["function"]["name"]
        function_args = json.loads(tool_call["function"]["arguments"])

        # Execute the tool
        if function_name == "web_search":
            tool_result = web_search(function_args.get("query", ""))
        else:
            tool_result = f"Unknown tool: {function_name}"

        # Add assistant message with tool call
        messages.append({
            "role": "assistant",
            "content": message.get("content"),
            "tool_calls": [tool_call]
        })

        # Add tool result message
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": tool_result
        })

        # Send follow-up request with tool result
        data["messages"] = messages
        resp = requests.post(url, headers=headers, json=data, timeout=120)
        resp.raise_for_status()
        response_data = resp.json()
        message = response_data["choices"][0]["message"]

    return message.get("content", "")


def web_search(query: str) -> str:
    """Perform a web search using Tavily API."""
    import requests
    try:
        tavily_key = os.getenv("TAVILY_API_KEY")
        if not tavily_key:
            return "Error: TAVILY_API_KEY not found in environment variables"
    except Exception:
        return "Error: TAVILY_API_KEY not found"

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": tavily_key,
        "query": query,
        "search_depth": "basic",
        "max_results": 5
    }

    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        results = resp.json().get("results", [])

        if not results:
            return "No results found"

        formatted = []
        for r in results:
            formatted.append(f"Title: {r.get('title', 'N/A')}\nURL: {r.get('url', 'N/A')}\nContent: {r.get('content', 'N/A')[:500]}")

        return "\n\n".join(formatted)
    except Exception as e:
        return f"Search error: {str(e)}"
