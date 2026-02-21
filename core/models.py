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
        self.coding_model = next((m for m in self.models if m.get("role") == "coding"), None)
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
        
        complex_keywords = ["analyze", "summarize", "multi-step", "reasoning", "extract"]
        for word in complex_keywords:
            if word in prompt.lower():
                complexity_score += 1
                
        if context and len(context) > 10:  # If conversation history is long
            complexity_score += 1

        return complexity_score >= 2

    def is_coding_task(self, prompt):
        coding_keywords = ["code", "script", "python", "bash", "javascript", "function", "debug", "html", "css", "docker", "api"]
        return any(word in prompt.lower() for word in coding_keywords)

    def generate(self, prompt, system_prompt="You are a helpful AI assistant.", context=None, tools=None):
        """
        Main generation entrypoint. Uses Ollama or LiteLLM based on config and complexity.
        """
        is_complex = self.evaluate_complexity(prompt, context)
        is_code = self.is_coding_task(prompt)
        
        selected_model = self.default_model
        
        if is_code and self.coding_model:
            selected_model = self.coding_model
        elif is_complex and self.complex_model:
            selected_model = self.complex_model
        elif not is_complex and not is_code and self.fast_model:
            selected_model = self.fast_model
            
        role_printed = selected_model.get('role', 'default')
        logging.info(f"Smart Routing -> Task: {'Coding' if is_code else ('Complex' if is_complex else 'Simple')} -> Selected Model: {selected_model['model']} ({selected_model['provider']} - {role_printed})")
        
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
            
            # Fallback parsing for models like llama3.2/qwen that sometimes output raw JSON text
            # instead of using the native tool calling schema when heavily prompted.
            if not tool_calls and content and "{" in content and "}" in content:
                try:
                    import re
                    decoder = json.JSONDecoder()
                    
                    # We look for '{' iteratively and try to decode a JSON object.
                    pos = 0
                    while pos < len(content):
                        # Find the next '{'
                        match = re.search(r'\{', content[pos:])
                        if not match:
                            break
                        start_idx = pos + match.start()
                        
                        try:
                            # Try to parse a full json object from this index
                            parsed, num_chars = decoder.raw_decode(content[start_idx:])
                            
                            # If successful, check if it resembles a tool call
                            if isinstance(parsed, dict) and ("function" in parsed or "name" in parsed):
                                func_name = parsed.get("function", {}).get("name") or parsed.get("name")
                                args = parsed.get("function", {}).get("arguments") or parsed.get("arguments", {})
                                
                                # Some models nest arguments under "parameters" instead of "arguments"
                                if not args and "parameters" in parsed:
                                    args = parsed.get("parameters", {})
                                
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
                                    # Strip the JSON from the conversational response
                                    content = content[:start_idx] + content[start_idx + num_chars:]
                                    # Don't increment pos, because we just shrank the string
                                    continue
                        except json.JSONDecodeError:
                            # Not a valid root JSON object, skip this '{'
                            pass
                        
                        pos = start_idx + 1

                except Exception as e:
                    logging.debug(f"Failed fallback JSON parsing: {e}")
                
            # Final cleanup of leftover whitespace from string replacements
            content = content.strip()
            
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
