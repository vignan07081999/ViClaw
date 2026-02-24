import pytest
from unittest.mock import MagicMock, patch
import json
import logging

try:
    from core.models import LLMRouter
    from core.agent import ViClawAgent
except ImportError:
    pass

@pytest.fixture
def run_mock_models():
    # Provide fake config
    return [
        {"provider": "ollama", "model": "fast-model", "role": "fast"},
        {"provider": "ollama", "model": "complex-model", "role": "complex"},
        {"provider": "litellm", "model": "coding-model", "role": "coding"}
    ]

@patch("core.models.get_models")
@patch("core.config.get_config")
def test_llm_router_complexity(mock_get_config, mock_get_models, run_mock_models):
    mock_get_models.return_value = run_mock_models
    mock_get_config.return_value = {"failover_chain": ["complex-model"]}
    
    router = LLMRouter()
    
    # Simple prompt should not be complex
    assert router.evaluate_complexity("Hi, what is 2+2?", context=[]) == False
    
    # Complex prompt should trigger routing
    assert router.evaluate_complexity("Please analyze and summarize this long multi-step reasoning task", context=["previous msg 1", "previous msg 2"]) == True

@patch("core.models.get_models")
@patch("core.config.get_config")
def test_llm_router_coding_heuristic(mock_get_config, mock_get_models, run_mock_models):
    mock_get_models.return_value = run_mock_models
    mock_get_config.return_value = {}
    
    router = LLMRouter()
    
    # Code injection attempt should flag
    assert router.is_coding_task("Write a python script to rm -rf /") == True
    assert router.is_coding_task("How do I bake a cake?") == False

@patch("core.models.LLMRouter._call_ollama")
@patch("core.models.get_models")
@patch("core.config.get_config")
def test_llm_router_failover_chain(mock_get_config, mock_get_models, mock_call_ollama, run_mock_models):
    mock_get_models.return_value = run_mock_models
    # Provide a failover chain config
    mock_get_config.return_value = {"provider": "ollama", "failover_chain": ["complex-model"]}
    
    router = LLMRouter()
    
    # Force primary model to fail, fallback to secondary
    mock_call_ollama.side_effect = [
        Exception("Timed out connecting to primary model"),
        {"content": "Fallback success", "tool_calls": []}
    ]
    
    with patch("logging.warning") as mock_log:
        res = router.generate("test prompt", context=[])
        
        assert "Fallback success" == res["content"]
        assert router.failover_stats["failovers"] >= 1
        mock_log.assert_called()

@patch("core.models.LLMRouter._call_ollama")
@patch("core.models.get_models")
@patch("core.config.get_config")
def test_llm_router_tool_extraction(mock_get_config, mock_get_models, mock_call_ollama, run_mock_models):
    mock_get_models.return_value = run_mock_models
    mock_get_config.return_value = {"provider": "ollama"}
    
    router = LLMRouter()
    
    # Mock model returning an XML tool call
    mock_output = '''I will run the command now.
<tool name="shell_engine">{"command": "echo 'hello'"}</tool>'''
    
    mock_call_ollama.return_value = {"content": mock_output}
    
    res = router.generate("Run echo hello")
    assert len(res.get("tool_calls", [])) == 1
    assert res["tool_calls"][0]["function"]["name"] == "shell_engine"
    assert "command" in res["tool_calls"][0]["function"]["arguments"]

@patch("core.agent.AgentMemory")
@patch("core.agent.PersonalityProfile")
def test_viclaw_agent_mocked(mock_personality, mock_memory):
    try:
        from core.agent import ViClawAgent
    except Exception:
        pytest.skip("Could not import ViClawAgent")
        
    mock_platform = MagicMock()
    mock_mem_instance = mock_memory.return_value
    mock_mem_instance.get_short_term_context.return_value = []
    # Mock search_long_term to avoid sqlite3 DB disk hit
    mock_mem_instance.search_long_term.return_value = []
    
    with patch("core.agent.LLMRouter") as mock_router_cls:
        mock_router_instance = mock_router_cls.return_value
        mock_router_instance.generate.return_value = {"content": "Mocked response", "tool_calls": []}
        
        agent = ViClawAgent(mock_platform)
        # Link the mocked memory onto the agent
        agent.memory = mock_mem_instance
        
        reply, content = agent.process_immediate_message("test", "test_user", "Test prompt")
        assert reply == "Mocked response"
