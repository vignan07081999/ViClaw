import logging
import json
import os
from litellm import completion
import ollama

from core.config import get_provider, get_model, get_api_key_env, get_ollama_url

class LLMRouter:
    def __init__(self):
        self.provider = get_provider()
        self.default_model = get_model()
        self.api_key = os.environ.get(get_api_key_env())
        self.ollama_url = get_ollama_url()
        
        # Optional fallback model (could be configured, hardcoding for clone demo)
        self.fallback_model = "gpt-4o-mini"
        
        if self.provider == "litellm" and not self.api_key:
            logging.warning(f"LiteLLM Provider chosen but API Key environment variable {get_api_key_env()} is not set.")

    def evaluate_complexity(self, prompt, context=None):
        """
        A heuristic function to evaluate if a task requires a larger model.
        In a real scenario, this could be a small classifier model.
        For this clone, we use simple rule-based heuristics.
        Returns: True if complex, False if simple.
        """
        complexity_score = 0
        if len(prompt) > 500:
            complexity_score += 1
        
        complex_keywords = ["analyze", "summarize", "code", "multi-step", "reasoning", "extract"]
        for word in complex_keywords:
            if word in prompt.lower():
                complexity_score += 1
                
        if context and len(context) > 10:  # If conversation history is long
            complexity_score += 1

        return complexity_score >= 2

    def generate(self, prompt, system_prompt="You are a helpful AI assistant.", context=None, tools=None):
        """
        Main generation entrypoint. Uses Ollama or LiteLLM based on config and complexity.
        """
        is_complex = self.evaluate_complexity(prompt, context)
        
        # Build messages payload
        messages = [{"role": "system", "content": system_prompt}]
        
        if context:
            # Assuming context is a list of dicts [{"role": "user"/"assistant", "content": "..."}]
            messages.extend(context)
            
        messages.append({"role": "user", "content": prompt})

        # Route to provider
        if self.provider == "ollama":
            # If it's a complex task but they strictly want local, we still use Ollama, but maybe a larger local model if configured.
            # For simplicity, stick to the configured model.
            return self._call_ollama(messages, tools=tools)
        
        elif self.provider == "litellm":
            use_model = self.fallback_model if is_complex else self.default_model
            return self._call_litellm(messages, model=use_model, tools=tools)

        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def _call_ollama(self, messages, tools=None):
        logging.info(f"Routing to Ollama (Model: {self.default_model}) at {self.ollama_url}")
        try:
            client = ollama.Client(host=self.ollama_url)
            
            # Prepare tools if any
            options = {}
            if tools:
                # Ollama support for tools depends on the version and model.
                options['tools'] = tools
                
            response = client.chat(model=self.default_model, messages=messages, **options)
            
            # Extract content and tool calls
            message = response.get('message', {})
            content = message.get('content', '')
            tool_calls = message.get('tool_calls', [])
            
            return {
                "content": content,
                "tool_calls": tool_calls
            }
        except Exception as e:
            logging.error(f"Ollama inference failed: {e}")
            return {"content": "I encountered an error connecting to my local model.", "tool_calls": []}

    def _call_litellm(self, messages, model, tools=None):
        logging.info(f"Routing to LiteLLM (Model: {model})")
        try:
            kwargs = {}
            if tools:
                kwargs["tools"] = tools
                
            response = completion(
                model=model,
                messages=messages,
                api_key=self.api_key,
                **kwargs
            )
            
            message = response.choices[0].message
            content = message.content or ""
            
            tool_calls = []
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tc in message.tool_calls:
                    tool_calls.append({
                        "function": {
                            "name": tc.function.name,
                            "arguments": json.loads(tc.function.arguments)
                        }
                    })
                    
            return {
                "content": content,
                "tool_calls": tool_calls
            }
        except Exception as e:
            logging.error(f"LiteLLM inference failed: {e}")
            return {"content": "I encountered an error connecting to the API.", "tool_calls": []}
