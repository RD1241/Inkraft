import os
from PIL import Image

outputs_dir = "outputs"
if not os.path.exists(outputs_dir):
    outputs_dir = "../outputs"

print(f"Scanning {outputs_dir}...")
if not os.path.exists(outputs_dir):
    print("Outputs directory does not exist!")
    exit(1)

subdirs = sorted(os.listdir(outputs_dir), reverse=True)
for subdir in subdirs[:10]:
    subdir_path = os.path.join(outputs_dir, subdir)
    if not os.path.isdir(subdir_path):
        continue
    print(f"\nSubdirectory: {subdir}")
    for file in os.listdir(subdir_path):
        file_path = os.path.join(subdir_path, file)
        if file.endswith((".png", ".jpg")):
            try:
                with Image.open(file_path) as img:
                    extrema = img.convert("L").getextrema()
                    print(f"  {file}: size={img.size}, mode={img.mode}, extrema={extrema}")
            except Exception as e:
                print(f"  {file}: Error reading: {e}")
