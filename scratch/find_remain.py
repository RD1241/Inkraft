import os
import re

SEARCH_PATHS = [
    r"d:\Project_I\NovelToComic",
    r"d:\Project_I\frontend-next"
]

EXCLUDE_DIRS = {
    '.git', 'node_modules', 'venv', '.next', 'out', 'dist', 'build', '__pycache__', '.pytest_cache', '.idea', '.vscode'
}

EXCLUDE_FILES = {
    'find_remain.py', 'occurrences.json', 'perform_rebrand.py', 'find_occurrences.py'
}

PATTERNS = [
    re.compile(r'NovelToComic', re.IGNORECASE),
    re.compile(r'Novel to Comic', re.IGNORECASE),
    re.compile(r'noveltocomic', re.IGNORECASE),
    re.compile(r'Novel-to-Comic', re.IGNORECASE)
]

def search_files():
    found_any = False
    for path in SEARCH_PATHS:
        if not os.path.exists(path):
            continue
        for root, dirs, files in os.walk(path):
            # Prune excluded directories
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            
            for file in files:
                if file in EXCLUDE_FILES:
                    continue
                # Ignore binary files or extensions that shouldn't be searched
                if file.endswith(('.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.zip', '.tar', '.gz', '.woff', '.woff2', '.ttf', '.eot')):
                    continue
                    
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    
                    for line_idx, line in enumerate(lines, 1):
                        for pattern in PATTERNS:
                            if pattern.search(line):
                                # Double check database table exclusions if any
                                # We shouldn't change database table/schema names if there are any specific matches.
                                # Let's print out the match.
                                print(f"MATCH: {file_path}:{line_idx}: {line.strip()}")
                                found_any = True
                                break
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
                    
    if not found_any:
        print("CONGRATULATIONS: No occurrences of the branding terms found!")

if __name__ == "__main__":
    search_files()
