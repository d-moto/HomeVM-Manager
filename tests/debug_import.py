import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

with open("error.log", "w") as f:
    try:
        f.write("Importing main...\n")
        import main
        f.write("Import successful\n")
    except SyntaxError as e:
        f.write(f"SyntaxError in {e.filename} at line {e.lineno}: {e.msg}\n")
    except Exception as e:
        f.write(f"Import failed: {e}\n")
        import traceback
        traceback.print_exc(file=f)
