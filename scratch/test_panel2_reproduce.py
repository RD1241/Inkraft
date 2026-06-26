import os
import sys
import fal_client

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

fal_key = os.environ.get("FAL_KEY") or getattr(settings, "FAL_KEY", None)
os.environ["FAL_KEY"] = fal_key

# We will use the already extracted elena_ref.png which we know is valid
ref_path = r"d:\Project_I\NovelToComic\outputs\20260605_223315\elena_ref.png"
uploaded_url = fal_client.upload_file(ref_path)
print(f"Uploaded reference URL: {uploaded_url}")

pos_prompt = "medium shot, neutral, Elena, same face, same outfit, same hairstyle, cinematic, soft studio lighting, gentle ambient glow, Neither spoke., manhwa webtoon illustration, soft digital coloring, detailed background"
neg_prompt = "1girl, girl, woman, female, breasts, cleavage, feminine face, robe, cloak, cape, dress, kimono, toga, gown, beard, facial hair, face mask, helmet, robotic arm, red clothing, red pants, ninja, modern clothing, sliding door, modern window, glass door, contemporary architecture, duplicate character, two people, extra limbs, deformed hands, bad anatomy, extra fingers, fused fingers, blurry, low quality, worst quality, watermark, text, signature, inconsistent outfit, gender swap, extra person"

print("Calling fal.ai API for reproduction...")
try:
    res = fal_client.subscribe(
        "fal-ai/fast-sdxl",
        arguments={
            "model_name": "Linaqruf/noobai-xl-v1.0",
            "prompt": pos_prompt,
            "negative_prompt": neg_prompt,
            "image_url": uploaded_url,
            "strength": 0.45,
            "image_size": {
                "width": 768,
                "height": 1024
            },
            "num_inference_steps": 25,
            "seed": 43
        }
    )
    print("API Response:")
    print(res)
    if "images" in res and len(res["images"]) > 0:
        print(f"Generated Image URL: {res['images'][0]['url']}")
except Exception as e:
    print(f"API Error: {e}")
