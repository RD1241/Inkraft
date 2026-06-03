import os

api_dir = r"D:\Project_I\NovelToComic\api"
for root, dirs, files in os.walk(api_dir):
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            with open(path, "r", encoding="utf-8") as file:
                content = file.read()
                if "HTTPBearer" in content or "get_current_user" in content or "Not authenticated" in content or "Depends" in content:
                    print(f"Match in {f}:")
                    for i, line in enumerate(content.splitlines()):
                        if any(k in line for k in ["HTTPBearer", "get_current_user", "Not authenticated", "Depends"]):
                            print(f"  Line {i+1}: {line}")
