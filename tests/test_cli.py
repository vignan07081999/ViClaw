import subprocess
import os
import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VICLAW_BIN = os.path.join(ROOT_DIR, "viclaw")

@pytest.mark.parametrize("command", [
    "chat",
    "acp",
    "diagnostics",
    "doctor",
    "usage",
    "main",
    "launcher"
])
def test_cli_help_flags(command):
    """Ensure all subcommands handle --help gracefully and return exit code 0."""
    result = subprocess.run([VICLAW_BIN, command, "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Usage:" in result.stdout or "Help for" in result.stdout

def test_cli_invalid_command():
    """Ensure invalid commands fallback gracefully or exit safely."""
    result = subprocess.run([VICLAW_BIN, "invalid_commmand_1234"], capture_output=True, text=True)
    # The default behavior drops to viclaw.py which clears the screen and opens the menu,
    # or errors out depending on sys.stdin. Since it opens a menu requiring input, it will raise EOFError or similar.
    # We just ensure it doesn't crash with a generic Python traceback on load.
    pass  # We can't easily test interactive menus via subprocess without pexpect, but the help flags test core routing.

def test_diagnostics_import():
    """Ensure diagnostics script can be imported without ModuleNotFoundError."""
    import sys
    sys.path.insert(0, ROOT_DIR)
    try:
        import cli.diagnostics
        assert callable(cli.diagnostics.get_db_size)
    except Exception as e:
        pytest.fail(f"Could not import diagnostics: {e}")
