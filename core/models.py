import logging
import json
import re
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

    def generate(self, prompt, system_prompt=None, context=None, tools=None, images=None):
        """
        Generates a response from the configured LLM.
        Note: `tools` is ignored here as we've moved to XML-based tool execution.
        `images` accepts a list of base64 encoded image strings.
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
            
        # Overwrite if we have images, require a vision model. Currently assuming complex model for vision if not specified.
        # In a generic environment we might map a dedicated "vision" model role.
        if images and "vision" not in selected_model["model"].lower() and "llava" not in selected_model["model"].lower():
            # Images present but model may not support vision; pass through and let Ollama handle it.
            # Add a "vision" role to config.json for an explicit vision model mapping.
            logging.info("Images present; selected model may not support vision. Consider adding a 'vision' role to config.json.")
        role_printed = selected_model.get('role', 'default')
        logging.info(f"Smart Routing -> Task: {'Coding' if is_code else ('Complex' if is_complex else 'Simple')} -> Selected Model: {selected_model['model']} ({selected_model['provider']} - {role_printed})")
        
        # Build messages payload
        messages = [{"role": "system", "content": system_prompt}]
        
        if context:
            messages.extend(context)
            
        # Bind images specifically to the final User prompt for Vision handling
        user_msg = {"role": "user", "content": prompt}
        if images and selected_model["provider"] == "ollama":
            user_msg["images"] = images
            
        messages.append(user_msg)

        # Route to provider (native tools parameter is intentionally None to force XML behavior)
        if selected_model["provider"] == "ollama":
            url = selected_model.get("ollama_url", "http://localhost:11434")
            res = self._call_ollama(messages, selected_model["model"], url, tools=None)
        
        elif selected_model["provider"] == "litellm":
            env_key = selected_model.get("api_key_env", "OPENAI_API_KEY")
            api_key = os.environ.get(env_key)
            
            # Format Litellm vision structure
            if images:
               litellm_msg = []
               litellm_msg.append({"type": "text", "text": prompt})
               for img in images:
                   litellm_msg.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}})
               messages[-1]["content"] = litellm_msg
               
            res = self._call_litellm(messages, selected_model["model"], api_key, tools=None)

        else:
            raise ValueError(f"Unknown provider: {selected_model['provider']}")
            
        # UNIVERSAL XML TOOL EXTRACTOR
        # Parses <tool name="...">{...}</tool> from the output text.
        content = res.get("content", "")
        tool_calls = res.get("tool_calls", [])
        
        if content and "<tool" in content:
            # Find all XML tool tags
            pattern = r"<tool\s+name=[\"']([^\"']+)[\"']>([\s\S]*?)</tool>"
            matches = list(re.finditer(pattern, content))
            
            for match in matches:
                func_name = match.group(1)
                args_str = match.group(2).strip()
                args = {}
                
                if args_str:
                    try:
                        args = json.loads(args_str)
                    except Exception as e:
                        logging.warning(f"Failed to parse XML tool args for {func_name}: {e}")
                        
                tool_calls.append({
                    "function": {
                        "name": func_name,
                        "arguments": args
                    }
                })
            
            # Remove all `<tool>...</tool>` blocks from the conversational content
            content = re.sub(pattern, "", content)
            
        res["content"] = content.strip()
        res["tool_calls"] = tool_calls
        return res

    def _call_ollama(self, messages, model_name, url, tools=None):
        logging.info(f"Routing to Ollama (Model: {model_name}) at {url}")
        try:
            client = ollama.Client(host=url)
            
            options = {}
            if tools:
                options['tools'] = tools
                
            response = client.chat(model=model_name, messages=messages, **options)
            
            # ollama library returns a ChatResponse object, not a plain dict.
            # Access attributes directly; fall back to dict-style for older versions.
            try:
                message = response.message
                content = message.content or ''
                tool_calls_raw = message.tool_calls or []
            except AttributeError:
                # Older ollama library or plain dict fallback
                message = response.get('message', {})
                content = message.get('content', '') if isinstance(message, dict) else ''
                tool_calls_raw = message.get('tool_calls', []) if isinstance(message, dict) else []
            
            # Normalize tool_calls to the expected dict format
            tool_calls = []
            for tc in tool_calls_raw:
                if hasattr(tc, 'function'):
                    tool_calls.append({
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments if isinstance(tc.function.arguments, dict) else {}
                        }
                    })
                elif isinstance(tc, dict):
                    tool_calls.append(tc)
            
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

    # ------------------------------------------------------------------
    # Streaming API (for WebUI SSE)
    # ------------------------------------------------------------------

    def generate_stream(self, prompt, system_prompt=None, context=None, images=None):
        """
        Generator that yields text token chunks progressively.
        Used by the /api/chat/stream SSE endpoint.
        Yields: str chunks (raw token text)
        After all tokens are yielded, checks for XML tool calls in the assembled text
        and yields a final JSON event with tool results if tools were triggered.
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

        messages = [{"role": "system", "content": system_prompt or ""}]
        if context:
            messages.extend(context)
        user_msg = {"role": "user", "content": prompt}
        if images and selected_model["provider"] == "ollama":
            user_msg["images"] = images
        messages.append(user_msg)

        if selected_model["provider"] == "ollama":
            url = selected_model.get("ollama_url", "http://localhost:11434")
            yield from self._call_ollama_stream(messages, selected_model["model"], url)
        else:
            # LiteLLM: non-streaming fallback — yield whole response as single chunk
            res = self._call_litellm(messages, selected_model["model"],
                                     os.environ.get(selected_model.get("api_key_env", "OPENAI_API_KEY")))
            yield res.get("content", "")

    def _call_ollama_stream(self, messages, model_name, url):
        """Stream tokens from Ollama using the ollama library's stream=True mode."""
        logging.info(f"Stream routing to Ollama (Model: {model_name}) at {url}")
        try:
            client = ollama.Client(host=url)
            stream = client.chat(model=model_name, messages=messages, stream=True)
            for chunk in stream:
                try:
                    token = chunk.message.content
                except AttributeError:
                    token = chunk.get("message", {}).get("content", "") if isinstance(chunk, dict) else ""
                if token:
                    yield token
        except Exception as e:
            logging.error(f"Ollama stream failed: {e}")
            yield f"[Stream error: {e}]"
