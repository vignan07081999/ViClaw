import sys
import traceback

def test_imports():
    targets = [
        "viclaw",
        "cli.chat",
        "cli.acp",
        "cli.diagnostics",
        "cli.doctor",
        "cli.usage",
        "webui.app",
        "main",
        "launcher"
    ]
    
    success = True
    for t in targets:
        try:
            __import__(t)
            print(f"✅ {t} imported successfully!")
        except Exception as e:
            print(f"❌ {t} failed to import:")
            traceback.print_exc()
            success = False
            
    if not success:
        sys.exit(1)
    print("\nAll modules passed static load tests.")
    
if __name__ == "__main__":
    test_imports()
