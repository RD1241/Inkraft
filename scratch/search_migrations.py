import os

search_dir = "."
found = False
for root, dirs, files in os.walk(search_dir):
    if "venv" in root or ".git" in root or ".next" in root or "node_modules" in root:
        continue
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "migrations" in content or "001_initial_schema" in content:
                        print(f"Found reference in: {path}")
                        found = True
            except Exception:
                pass

if not found:
    print("No automated migration runner references found in Python code.")
