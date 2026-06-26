import os
import sys
import httpx

# Add project root to sys.path to ensure configuration imports work correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from config import settings
except ImportError:
    settings = None

def main():
    print("[FalAI Test Connection] Initializing test script...")
    
    # Retrieve the FAL key
    fal_key = os.environ.get("FAL_KEY")
    if not fal_key and settings:
        fal_key = getattr(settings, "FAL_KEY", None)
        
    if not fal_key or fal_key == "your_fal_api_key_here" or fal_key.strip() == "":
        print("[FalAI Test Connection] FAL_KEY is not set or is still configured with placeholder.")
        print("Please configure a valid FAL_KEY in your .env file to run this test.")
        return

    # Ensure FAL_KEY is placed in os.environ for fal_client to pick up
    os.environ["FAL_KEY"] = fal_key

    try:
        print("[FalAI Test Connection] Importing fal-client...")
        import fal_client
    except ImportError:
        print("[FalAI Test Connection] fal-client is not installed in the current environment.")
        print("Please run: pip install -r requirements.txt")
        return

    prompt = "a cinematic manga drawing of a futuristic city"
    endpoint = "fal-ai/fast-sdxl"
    model_name = "cagliostrolab/animagine-xl-3.1"
    
    print(f"[FalAI Test Connection] Sending test request to endpoint '{endpoint}' with model '{model_name}'...")
    print(f"[FalAI Test Connection] Prompt: '{prompt}'")
    
    try:
        # Submit the request
        result = fal_client.subscribe(
            endpoint,
            arguments={
                "prompt": prompt,
                "negative_prompt": "lowres, bad anatomy, text, error, worst quality",
                "model_name": model_name,
                "image_size": {
                    "width": 512,
                    "height": 512
                },
                "seed": 42
            }
        )
        
        if not result or "images" not in result or len(result["images"]) == 0:
            raise ValueError(f"Unexpected API response structure: {result}")
            
        image_url = result["images"][0]["url"]
        print(f"[FalAI Test Connection] Image successfully generated! URL: {image_url}")
        
        # Download the file
        print("[FalAI Test Connection] Downloading generated image...")
        response = httpx.get(image_url)
        response.raise_for_status()
        
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_outputs", "fal_test.png")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, "wb") as f:
            f.write(response.content)
            
        print(f"[FalAI Test Connection] Image saved successfully to: {output_path}")
        print(f"[FalAI] Panel generated — model: {model_name}, estimated cost: $0.003")
        print("[FalAI Test Connection] TEST PASSED SUCCESSFULLY.")
        
    except Exception as e:
        print(f"[FalAI Test Connection] TEST FAILED: API call failed with error: {e}")

if __name__ == "__main__":
    main()
