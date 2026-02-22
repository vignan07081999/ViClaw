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
        self.failover_stats = {"attempts": 0, "failovers": 0, "last_failover": None}
        # Build ordered failover chain: [selected, ...fallback_chain models..., default]
        from core.config import get_config as _gc
        cfg = _gc()
        fallback_names = cfg.get("failover_chain", [])  # list of model names from config
        self._fallback_models = [m for name in fallback_names for m in self.models if m.get("model") == name]

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

    def _select_model(self, prompt, context):
        """Returns the route-selected model based on complexity/coding heuristics."""
        is_complex = self.evaluate_complexity(prompt, context)
        is_code = self.is_coding_task(prompt)
        selected = self.default_model
        if is_code and self.coding_model:
            selected = self.coding_model
        elif is_complex and self.complex_model:
            selected = self.complex_model
        elif not is_complex and not is_code and self.fast_model:
            selected = self.fast_model
        return selected

    def _build_failover_chain(self, selected):
        """Build ordered list of models to try: selected → fallback_chain → default."""
        chain = [selected]
        for m in self._fallback_models:
            if m is not selected and m not in chain:
                chain.append(m)
        if self.default_model not in chain:
            chain.append(self.default_model)
        return chain

    def _call_model(self, messages, model_cfg, images=None):
        """Dispatch to Ollama or LiteLLM based on provider."""
        if model_cfg["provider"] == "ollama":
            url = model_cfg.get("ollama_url", "http://localhost:11434")
            return self._call_ollama(messages, model_cfg["model"], url)
        elif model_cfg["provider"] == "litellm":
            api_key = os.environ.get(model_cfg.get("api_key_env", "OPENAI_API_KEY"))
            return self._call_litellm(messages, model_cfg["model"], api_key)
        else:
            raise ValueError(f"Unknown provider: {model_cfg['provider']}")

    def generate(self, prompt, system_prompt=None, context=None, tools=None, images=None):
        """
        Generates a response from the configured LLM with automatic failover.
        Tries: route-selected model → fallback_chain → default model (last resort).
        `tools` is ignored (we use XML-based tool execution).
        `images` accepts a list of base64 encoded image strings.
        """
        selected = self._select_model(prompt, context)
        role_printed = selected.get("role", "default")
        logging.info(f"Smart Routing → Selected: {selected['model']} ({selected['provider']} - {role_printed})")

        if images and "vision" not in selected["model"].lower() and "llava" not in selected["model"].lower():
            logging.info("Images present; selected model may not support vision. Consider a 'vision' role in config.json.")

        messages = [{"role": "system", "content": system_prompt or ""}]
        if context:
            messages.extend(context)
        user_msg = {"role": "user", "content": prompt}
        if images and selected["provider"] == "ollama":
            user_msg["images"] = images
        elif images and selected["provider"] == "litellm":
            litellm_parts = [{"type": "text", "text": prompt}]
            for img in images:
                litellm_parts.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}})
            user_msg["content"] = litellm_parts
        messages.append(user_msg)

        # ── Failover loop ──────────────────────────────────────────────
        chain = self._build_failover_chain(selected)
        last_error = None
        for i, model_cfg in enumerate(chain):
            self.failover_stats["attempts"] += 1
            try:
                if i > 0:
                    self.failover_stats["failovers"] += 1
                    import datetime
                    self.failover_stats["last_failover"] = datetime.datetime.now().isoformat()
                    logging.warning(f"Failover #{i}: trying {model_cfg['model']} after {last_error}")
                res = self._call_model(messages, model_cfg, images)
                if res.get("content") and not res["content"].startswith("I encountered an error"):
                    if i > 0:
                        res["_failover_used"] = model_cfg["model"]
                    break
            except Exception as e:
                last_error = e
                logging.error(f"Model {model_cfg['model']} failed: {e}")
                res = {"content": str(e), "tool_calls": []}
        else:
            res = {"content": "All models in the failover chain failed. Please check your Ollama/API configuration.", "tool_calls": []}
            
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
        Generator that yields text token chunks progressively with failover support.
        Tries: route-selected model → fallback_chain → default model.
        """
        selected = self._select_model(prompt, context)
        logging.info(f"Stream routing → {selected['model']} ({selected['provider']})")

        messages = [{"role": "system", "content": system_prompt or ""}]
        if context:
            messages.extend(context)
        user_msg = {"role": "user", "content": prompt}
        if images and selected["provider"] == "ollama":
            user_msg["images"] = images
        messages.append(user_msg)

        chain = self._build_failover_chain(selected)
        last_error = None
        for i, model_cfg in enumerate(chain):
            try:
                if i > 0:
                    self.failover_stats["failovers"] += 1
                    import datetime
                    self.failover_stats["last_failover"] = datetime.datetime.now().isoformat()
                    logging.warning(f"Stream failover #{i}: trying {model_cfg['model']}")
                    yield f"[Failover → {model_cfg['model']}] "

                if model_cfg["provider"] == "ollama":
                    url = model_cfg.get("ollama_url", "http://localhost:11434")
                    # Test if the stream produces at least one token before committing
                    token_count = 0
                    for token in self._call_ollama_stream(messages, model_cfg["model"], url):
                        if token.startswith("[Stream error:") and token_count == 0:
                            raise RuntimeError(token)
                        token_count += 1
                        yield token
                    return  # success — done
                else:
                    # LiteLLM: non-streaming fallback
                    res = self._call_litellm(messages, model_cfg["model"],
                                             os.environ.get(model_cfg.get("api_key_env", "OPENAI_API_KEY")))
                    content = res.get("content", "")
                    if content and not content.startswith("I encountered an error"):
                        yield content
                        return
                    raise RuntimeError(content)
            except Exception as e:
                last_error = e
                logging.error(f"Stream model {model_cfg['model']} failed: {e}")

        yield f"[All models failed. Last error: {last_error}]"

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
