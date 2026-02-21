import logging
import json
import os
from litellm import completion
import ollama

from core.config import get_models

class LLMRouter:
    def __init__(self):
        self.models = get_models()
        self.fast_model = next((m for m in self.models if m.get("role") == "fast"), None)
        self.complex_model = next((m for m in self.models if m.get("role") == "complex"), None)
        self.default_model = next((m for m in self.models if m.get("role") == "default"), self.models[0])

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
        
        selected_model = self.default_model
        if is_complex and self.complex_model:
            selected_model = self.complex_model
        elif not is_complex and self.fast_model:
            selected_model = self.fast_model
            
        logging.info(f"Smart Routing -> Task Complexity: {'High' if is_complex else 'Low'} -> Selected Model: {selected_model['model']} ({selected_model['provider']})")
        
        # Build messages payload
        messages = [{"role": "system", "content": system_prompt}]
        
        if context:
            messages.extend(context)
            
        messages.append({"role": "user", "content": prompt})

        # Route to provider
        if selected_model["provider"] == "ollama":
            url = selected_model.get("ollama_url", "http://localhost:11434")
            return self._call_ollama(messages, selected_model["model"], url, tools=tools)
        
        elif selected_model["provider"] == "litellm":
            env_key = selected_model.get("api_key_env", "OPENAI_API_KEY")
            api_key = os.environ.get(env_key)
            return self._call_litellm(messages, selected_model["model"], api_key, tools=tools)

        else:
            raise ValueError(f"Unknown provider: {selected_model['provider']}")

    def _call_ollama(self, messages, model_name, url, tools=None):
        logging.info(f"Routing to Ollama (Model: {model_name}) at {url}")
        try:
            client = ollama.Client(host=url)
            
            options = {}
            if tools:
                options['tools'] = tools
                
            response = client.chat(model=model_name, messages=messages, **options)
            
            message = response.get('message', {})
            content = message.get('content', '')
            tool_calls = message.get('tool_calls', [])
            
            # Fallback parsing for models like llama3.2 that sometimes output raw JSON text
            # instead of using the native tool calling schema when heavily prompted.
            if not tool_calls and content and "{" in content and "}" in content:
                try:
                    import re
                    # Look for potential JSON tool execution blocks
                    match = re.search(r'\{.*\}', content, re.DOTALL)
                    if match:
                        potential_json = match.group(0)
                        parsed = json.loads(potential_json)
                        if "function" in parsed or "name" in parsed:
                            # It tried to output a tool call manually
                            func_name = parsed.get("function", {}).get("name") or parsed.get("name")
                            args = parsed.get("function", {}).get("arguments") or parsed.get("arguments", {})
                            if isinstance(args, str):
                                try:
                                    args = json.loads(args)
                                except:
                                    pass
                            
                            if func_name:
                                tool_calls.append({
                                    "function": {
                                        "name": func_name,
                                        "arguments": args
                                    }
                                })
                                content = content.replace(potential_json, "").strip() # Remove the JSON from the conversational response
                except Exception as e:
                    logging.debug(f"Failed fallback JSON parsing: {e}")
            
            return {
                "content": content,
                "tool_calls": tool_calls
            }
        except Exception as e:
            logging.error(f"Ollama inference failed: {e}")
            return {"content": "I encountered an error connecting to my local model.", "tool_calls": []}

    def _call_litellm(self, messages, model, api_key, tools=None):
        logging.info(f"Routing to LiteLLM (Model: {model})")
        try:
            kwargs = {}
            if tools:
                kwargs["tools"] = tools
                
            response = completion(
                model=model,
                messages=messages,
                api_key=api_key,
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
