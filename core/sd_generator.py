"""
sd_generator.py
---------------
Image generation with:
  - Style-based model routing  (MODEL_MAP in settings)
  - Model caching (avoids repeated loads across panels)
  - Conditional ControlNet/pose (action scenes only, random pose variation)
  - IP-Adapter reference conditioning (panels 2+, skipped for single-panel)
  - Dynamic IP scale (0.3 action / 0.5 calm)
  - No hard-coded poses per panel index
"""
import os
import random
import torch
from diffusers import (
    StableDiffusionImg2ImgPipeline,
    StableDiffusionPipeline,
    StableDiffusionXLPipeline,
    DPMSolverMultistepScheduler,
    ControlNetModel,
    StableDiffusionControlNetPipeline,
)
from PIL import Image, ImageDraw
from config import settings


# ---------------------------------------------------------------------------
# Pose skeleton helpers (only created when needed)
# ---------------------------------------------------------------------------

def _draw_pose(pose_type: int) -> Image.Image:
    img  = Image.new("RGB", (512, 512), "black")
    draw = ImageDraw.Draw(img)
    if pose_type == 0:          # UPRIGHT_STANDING
        draw.line([(256, 100), (256, 300)], fill="red",   width=5)
        draw.line([(256, 150), (200, 250)], fill="green", width=5)
        draw.line([(256, 150), (312, 250)], fill="blue",  width=5)
        draw.line([(256, 300), (220, 450)], fill="green", width=5)
        draw.line([(256, 300), (292, 450)], fill="blue",  width=5)
        draw.ellipse([(236, 50), (276, 90)], fill="red")
    elif pose_type == 1:        # FORWARD_LEAN
        draw.ellipse([(186, 100), (226, 140)], fill="red")
        draw.line([(206, 140), (280, 280)], fill="red", width=5)
        draw.line([(220, 170), (160, 260)], fill="green", width=5)
        draw.line([(220, 170), (290, 230)], fill="blue", width=5)
        draw.line([(280, 280), (240, 430)], fill="green", width=5)
        draw.line([(280, 280), (340, 420)], fill="blue", width=5)
    elif pose_type == 2:        # ACTION_TWIST
        draw.ellipse([(236, 60), (276, 100)], fill="red")
        draw.line([(256, 100), (240, 280)], fill="red", width=5)
        draw.line([(250, 140), (160, 100)], fill="green", width=5)
        draw.line([(250, 140), (340, 220)], fill="blue", width=5)
        draw.line([(240, 280), (160, 400)], fill="green", width=5)
        draw.line([(240, 280), (320, 430)], fill="blue", width=5)
    elif pose_type == 3:        # RELAXED_SITTING
        draw.ellipse([(236, 120), (276, 160)], fill="red")
        draw.line([(256, 160), (256, 320)], fill="red", width=5)
        draw.line([(256, 200), (200, 290)], fill="green", width=5)
        draw.line([(256, 200), (312, 290)], fill="blue", width=5)
        draw.line([(256, 320), (180, 320), (180, 450)], fill="green", width=5)
        draw.line([(256, 320), (332, 320), (332, 450)], fill="blue", width=5)
    elif pose_type == 4:        # COWERING_FEARFUL
        draw.ellipse([(216, 220), (256, 260)], fill="red")
        draw.line([(236, 260), (276, 360)], fill="red", width=5)
        draw.line([(250, 280), (210, 210), (240, 190)], fill="green", width=5)
        draw.line([(250, 280), (290, 210), (260, 190)], fill="blue", width=5)
        draw.line([(276, 360), (220, 340), (210, 450)], fill="green", width=5)
        draw.line([(276, 360), (320, 350), (310, 450)], fill="blue", width=5)
    elif pose_type == 5:        # REACHING_EXTENDING
        draw.ellipse([(286, 80), (326, 120)], fill="red")
        draw.line([(306, 120), (220, 280)], fill="red", width=5)
        draw.line([(280, 160), (420, 60)], fill="green", width=5)
        draw.line([(280, 160), (200, 200)], fill="blue", width=5)
        draw.line([(220, 280), (280, 430)], fill="green", width=5)
        draw.line([(220, 280), (120, 360)], fill="blue", width=5)
    elif pose_type == 6:        # CONFRONTATION
        draw.ellipse([(236, 70), (276, 110)], fill="red")
        draw.line([(256, 110), (256, 280)], fill="red", width=5)
        draw.line([(256, 150), (180, 180), (170, 240)], fill="green", width=5)
        draw.line([(256, 150), (330, 160), (380, 160)], fill="blue", width=5)
        draw.line([(256, 280), (180, 450)], fill="green", width=5)
        draw.line([(256, 280), (332, 450)], fill="blue", width=5)
    elif pose_type == 7:        # GROUND_FALLEN
        draw.ellipse([(100, 410), (140, 450)], fill="red")
        draw.line([(140, 430), (320, 430)], fill="red", width=5)
        draw.line([(180, 430), (150, 380)], fill="green", width=5)
        draw.line([(180, 430), (220, 450)], fill="blue", width=5)
        draw.line([(320, 430), (380, 400), (420, 440)], fill="green", width=5)
        draw.line([(320, 430), (450, 450)], fill="blue", width=5)
    else:                       # fallback
        draw.line([(256, 150), (256, 350)], fill="red",   width=5)
        draw.line([(256, 200), (200, 300)], fill="green", width=5)
        draw.line([(256, 200), (312, 250)], fill="blue",  width=5)
        draw.line([(256, 350), (220, 450)], fill="green", width=5)
        draw.line([(256, 350), (292, 450)], fill="blue",  width=5)
        draw.ellipse([(236, 80), (276, 120)], fill="red")
    return img


class PoseLibrary:
    """Lightweight registry of available pose types.
    Pre-generates 8 distinct OpenPose-format skeletons on 512x512 black canvas at init time.
    """
    def __init__(self):
        self.poses: dict[int, Image.Image] = {}
        for pose_type in range(8):
            self.poses[pose_type] = _draw_pose(pose_type)

    def random_pose(self) -> int:
        return random.choice(list(self.poses.keys()))

    def get_pose_image(self, pose_type: int) -> Image.Image:
        return self.poses.get(pose_type, self.poses[0])


# ---------------------------------------------------------------------------
# SDGenerator
# ---------------------------------------------------------------------------

ACTION_TRIGGER_WORDS = (
    # Each entry is a stem — startswith() covers all conjugations
    "attack",   # attack / attacks / attacked / attacking
    "fight",    # fight  / fights  / fighting  (fought → fo*, miss is ok)
    "jump",     # jump   / jumps   / jumped    / jumping
    "dash",     # dash   / dashes  / dashed    / dashing
    "strik",    # strike / strikes / struck    / striking
    "slam",     # slam   / slams   / slammed   / slamming
    "slash",    # slash  / slashes / slashed   / slashing
    "smash",    # smash  / smashes / smashing
    "charg",    # charge / charges / charged   / charging
    "kick",     # kick   / kicks   / kicked    / kicking
    "punch",    # punch  / punches / punching
    "clash",    # clash  / clashes / clashing
    "battl",    # battle / battles / battling
    "combat",   # combat (no conjugation needed)
    "lunge",    # lunge  / lunges  / lunging
)


def should_use_pose(action: str) -> bool:
    """Return True if the action text implies a dynamic pose is needed.

    Uses stem-prefix matching so that all conjugations are covered:
      attack / attacks / attacked / attacking  → 'attack'
      strike / strikes / struck / striking     → 'strik'
      dash   / dashes  / dashed / dashing      → 'dash'
      etc.
    """
    action_lower = action.lower()
    words = action_lower.replace(",", " ").replace(".", " ").split()
    return any(
        word.startswith(trigger)
        for word in words
        for trigger in ACTION_TRIGGER_WORDS
    )


# ---------------------------------------------------------------------------
# SDGenerator
# ---------------------------------------------------------------------------

# SDXL model IDs — these need a completely different generation path
_SDXL_MODEL_IDS = {
    "stabilityai/stable-diffusion-xl-base-1.0",
    "stabilityai/stable-diffusion-xl-refiner-1.0",
}


class SDGenerator:

    def __init__(self, model_id: str = None):
        self.model_id            = model_id or settings.SD_MODEL_ID
        self.device              = "cuda" if torch.cuda.is_available() else "cpu"
        self.pipeline            = None
        self.img2img_pipeline    = None
        self.ip_adapter_loaded   = False
        self._controlnet_setting = getattr(settings, "SD_CONTROLNET_ENABLED", False)  # master setting
        self.controlnet_enabled  = self._controlnet_setting
        self._is_sdxl            = False   # True when an SDXL model is active
        self.ip_reference_image  = None
        self._active_model_id    = None   # tracks which model is loaded
        # in-memory model cache — avoids re-loading same style in one session
        self.loaded_models: dict = {}
        # Pose library — random.choice(self.pose_library.poses) for variation
        self.pose_library        = PoseLibrary()

    # ------------------------------------------------------------------
    # Model loading / unloading
    # ------------------------------------------------------------------

    def _resolve_model_id(self, style: str = None) -> str:
        """Return the correct model ID for the requested style.
        Patch 6: validates style against MODEL_MAP, falls back to default.
        """
        model_map   = getattr(settings, "MODEL_MAP", {})
        default_id  = self.model_id
        if not style:
            return default_id
        # Validate style — if unknown, use default
        style_lower = style.lower()
        if style_lower not in model_map:
            print(f"[SD] Unknown style '{style}', falling back to default model.")
            return default_id
        return model_map[style_lower]

    def load_model(self, style: str = None):
        target_id = self._resolve_model_id(style)

        # Return cached pipeline if already loaded for this model
        if target_id in self.loaded_models:
            if self.pipeline is not self.loaded_models[target_id]:
                self.pipeline         = self.loaded_models[target_id]
                self._active_model_id = target_id
                self._is_sdxl         = target_id in _SDXL_MODEL_IDS
            return

        # Different model requested — unload current first
        if self.pipeline is not None:
            self.unload_model()

        # Always reset controlnet flag from master setting at start of each load
        self.controlnet_enabled = self._controlnet_setting
        self._is_sdxl = target_id in _SDXL_MODEL_IDS

        # SDXL cannot use SD1.5 ControlNet or IP-Adapter — force-disable both
        if self._is_sdxl:
            self.controlnet_enabled = False
            print(f"[SD] SDXL model detected — ControlNet and IP-Adapter disabled.")

        dtype = torch.float16 if self.device == "cuda" else torch.float32

        # HF_HOME is set in settings.py → all downloads go to D:\AI_Models\HuggingFace
        hf_home = getattr(settings, "HF_HOME", "D:\\AI_Models\\HuggingFace")

        def _load_plain(model_id: str):
            """Try local cache first; if missing, download to HF_HOME on D drive."""
            is_xl = model_id in _SDXL_MODEL_IDS
            pipe_cls = StableDiffusionXLPipeline if is_xl else StableDiffusionPipeline
            
            try:
                return pipe_cls.from_pretrained(
                    model_id,
                    torch_dtype=dtype,
                    safety_checker=None if not is_xl else "not_applicable", # SDXL doesn't use standard safety_checker
                    token=settings.HF_TOKEN,
                    local_files_only=True,
                )
            except Exception:
                print(f"[SD] '{model_id}' not in local cache — downloading to {hf_home} ...")
                return pipe_cls.from_pretrained(
                    model_id,
                    torch_dtype=dtype,
                    safety_checker=None if not is_xl else "not_applicable",
                    token=settings.HF_TOKEN,
                    local_files_only=False,
                )

        def _load_controlnet(controlnet_id: str) -> "ControlNetModel":
            """Try local cache first; download if missing."""
            try:
                return ControlNetModel.from_pretrained(
                    controlnet_id,
                    torch_dtype=dtype,
                    token=settings.HF_TOKEN,
                    local_files_only=True,
                )
            except Exception:
                print(f"[SD] ControlNet '{controlnet_id}' not cached — downloading to {hf_home} ...")
                return ControlNetModel.from_pretrained(
                    controlnet_id,
                    torch_dtype=dtype,
                    token=settings.HF_TOKEN,
                    local_files_only=False,
                )

        # --- Layer 1: Try requested style model (+ ControlNet if enabled) --
        print(f"[SD] Loading model: {target_id} on {self.device}")
        try:
            if self.controlnet_enabled:
                print(f"[SD] Loading ControlNet: {settings.SD_CONTROLNET_MODEL_ID}")
                controlnet    = _load_controlnet(settings.SD_CONTROLNET_MODEL_ID)
                self.pipeline = StableDiffusionControlNetPipeline.from_pretrained(
                    target_id,
                    controlnet=controlnet,
                    torch_dtype=dtype,
                    safety_checker=None,
                    token=settings.HF_TOKEN,
                    local_files_only=False,   # allow download on first run
                )
            else:
                self.pipeline = _load_plain(target_id)

        except Exception as e1:
            print(f"[SD] Warning: Could not load '{target_id}' with ControlNet — {e1}")

            # --- Layer 2: Disable ControlNet, retry style model plain -------
            if self.controlnet_enabled:
                print("[SD] Retrying without ControlNet ...")
                self.controlnet_enabled = False
                try:
                    self.pipeline = _load_plain(target_id)
                except Exception as e2:
                    print(f"[SD] Warning: Style model '{target_id}' failed — {e2}")
                    self.pipeline = None

            # --- Layer 3: Fall back to default model (dreamshaper-8) --------
            if self.pipeline is None:
                fallback_id = settings.SD_MODEL_ID
                print(f"[SD] Falling back to default model: {fallback_id}")
                try:
                    self.pipeline = _load_plain(fallback_id)
                    target_id = fallback_id
                except Exception as e3:
                    raise RuntimeError(
                        f"[SD] Critical: Default model '{fallback_id}' could not load. "
                        f"Check internet connection and HF_HOME={hf_home}. Error: {e3}"
                    )

        self.pipeline.scheduler = DPMSolverMultistepScheduler.from_config(
            self.pipeline.scheduler.config,
            algorithm_type="dpmsolver++",
            use_karras_sigmas=True,
        )

        if getattr(settings, "SD_IP_ADAPTER_ALWAYS_ON", False):
            self._try_load_ip_adapter()

        if self.device == "cuda":
            self.pipeline.enable_model_cpu_offload()
            if hasattr(self.pipeline, "vae") and self.pipeline.vae is not None:
                self.pipeline.vae.enable_slicing()
                self.pipeline.vae.enable_tiling()
            try:
                self.pipeline.enable_xformers_memory_efficient_attention()
            except Exception:
                pass
        else:
            self.pipeline.to("cpu")

        self._active_model_id = target_id
        # Patch 1: store in cache
        self.loaded_models[target_id] = self.pipeline

    def unload_model(self):
        if self.pipeline:
            # Remove from cache too
            self.loaded_models.pop(self._active_model_id, None)
            del self.pipeline
            self.pipeline = None
        if self.img2img_pipeline:
            del self.img2img_pipeline
            self.img2img_pipeline = None
        self.ip_adapter_loaded  = False
        self.ip_reference_image = None
        self._active_model_id   = None
        self._is_sdxl           = False
        # Always restore controlnet flag from master setting on unload
        self.controlnet_enabled = self._controlnet_setting
        
        # Explicit garbage collection to prevent VRAM hoarding
        import gc
        gc.collect()
        
        if self.device == "cuda":
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()

    # ------------------------------------------------------------------
    # IP-Adapter
    # ------------------------------------------------------------------

    def _try_load_ip_adapter(self) -> bool:
        if self.ip_adapter_loaded or self.pipeline is None:
            return self.ip_adapter_loaded

        adapter_id = getattr(settings, "SD_IP_ADAPTER_MODEL_ID", None)
        if not adapter_id or not hasattr(self.pipeline, "load_ip_adapter"):
            return False

        try:
            kwargs = {}
            if getattr(settings, "SD_IP_ADAPTER_SUBFOLDER", None):
                kwargs["subfolder"] = settings.SD_IP_ADAPTER_SUBFOLDER
            if getattr(settings, "SD_IP_ADAPTER_WEIGHT_NAME", None):
                kwargs["weight_name"] = settings.SD_IP_ADAPTER_WEIGHT_NAME
            self.pipeline.load_ip_adapter(
                adapter_id,
                token=settings.HF_TOKEN,
                local_files_only=True,
                **kwargs,
            )
            self.pipeline.set_ip_adapter_scale(
                getattr(settings, "SD_IP_ADAPTER_WEIGHT", 0.45)
            )
            self.ip_adapter_loaded = True
            print("[SD] IP-Adapter loaded.")
            return True
        except Exception as exc:
            print(f"[SD] IP-Adapter unavailable: {exc}")
            return False

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _generator(self, seed: int) -> torch.Generator:
        return torch.Generator(device="cpu").manual_seed(seed)

    def create_base_latents(self, seed: int = 42):
        generator = torch.Generator(device="cpu").manual_seed(seed)
        return torch.randn(
            (1, 4, settings.SD_HEIGHT // 8, settings.SD_WIDTH // 8),
            generator=generator,
            device="cpu",
            dtype=torch.float32,
        )

    def get_prompt_embeds(self, prompt: str, negative_prompt: str):
        tokenizer    = self.pipeline.tokenizer
        text_encoder = self.pipeline.text_encoder

        def encode(text):
            tokens     = tokenizer(text, add_special_tokens=False).input_ids
            chunk_size = tokenizer.model_max_length - 2
            chunks     = [tokens[i:i + chunk_size] for i in range(0, max(len(tokens), 1), chunk_size)]
            embeds = []
            for chunk in chunks:
                chunk = [tokenizer.bos_token_id] + chunk + [tokenizer.eos_token_id]
                chunk += [tokenizer.pad_token_id] * (tokenizer.model_max_length - len(chunk))
                tensor = torch.tensor([chunk], dtype=torch.long, device=text_encoder.device)
                with torch.no_grad():
                    embed = text_encoder(tensor)[0].to(
                        dtype=self.pipeline.unet.dtype, device=self.device
                    )
                    embeds.append(embed)
            return torch.cat(embeds, dim=1)

        p = encode(prompt)
        n = encode(negative_prompt)
        empty = encode("")
        while n.shape[1] < p.shape[1]:
            n = torch.cat([n, empty], dim=1)
        while p.shape[1] < n.shape[1]:
            p = torch.cat([p, empty], dim=1)
        return p, n

    def extract_character_anchor(self, image_path: str, output_path: str):
        image  = Image.open(image_path).convert("RGB")
        w, h   = image.size
        cw, ch = int(w * 0.60), int(h * 0.80)
        l      = max((w - cw) // 2, 0)
        t      = max((h - ch) // 2, 0)
        anchor = image.crop((l, t, min(l + cw, w), min(t + ch, h))).resize(
            (settings.SD_WIDTH, settings.SD_HEIGHT), Image.Resampling.LANCZOS
        )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        anchor.save(output_path)
        self.ip_reference_image = anchor
        return output_path

    # ------------------------------------------------------------------
    # Core generation
    # ------------------------------------------------------------------

    def generate_image(
        self,
        positive_prompt: str,
        negative_prompt: str,
        output_path: str,
        seed: int = 42,
        reference_image_path: str = None,
        reference_strength: float = None,
        base_latents=None,
        scene_id: int = 1,
        panel_index: int = 0,
        style: str = None,
        action: str = "",
        panel_count: int = None,
        layout_type: str = None,
        panel_width: int = 768,
        panel_height: int = 1024,
        focus_character: str = "",
        job_id: str = "",
    ):
        # Ensure correct model is loaded for the requested style
        self.load_model(style=style)

        generator = self._generator(seed)

        # Load reference image for IP-Adapter if provided
        if reference_image_path:
            self.ip_reference_image = Image.open(reference_image_path).convert("RGB").resize(
                (settings.SD_WIDTH, settings.SD_HEIGHT), Image.Resampling.LANCZOS
            )
        elif panel_index == 0:
            # Clear reference for the first panel of a new sequence
            self.ip_reference_image = None

        # ================================================================
        # SDXL PATH — plain string prompts, no ControlNet, no IP-Adapter
        # SDXL expects (prompt, negative_prompt) strings + pooled_prompt_embeds
        # which are built internally. Passing prompt_embeds without
        # pooled_prompt_embeds causes 'NoneType is not iterable' crashes.
        # ================================================================
        if self._is_sdxl:
            try:
                # SDXL uses 1024x1024 natively; clamp to avoid OOM on 6 GB VRAM
                w = min(settings.SD_WIDTH,  1024)
                h = min(settings.SD_HEIGHT, 1024)
                image = self.pipeline(
                    prompt=positive_prompt,
                    negative_prompt=negative_prompt,
                    generator=generator,
                    num_inference_steps=settings.SD_INFERENCE_STEPS,
                    guidance_scale=settings.SD_GUIDANCE_SCALE,
                    width=w,
                    height=h,
                ).images[0]
            except Exception as exc:
                print(f"[SD] SDXL generation failed: {exc}")
                raise
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            image.save(output_path)
            return output_path

        # ================================================================
        # SD 1.5 PATH — prompt_embeds, ControlNet, IP-Adapter
        # ================================================================

        # --- IP-Adapter kwargs -------------------------------------------
        # CRITICAL: When IP-Adapter is loaded, ip_adapter_image MUST always be
        # passed — omitting it causes 'NoneType is not iterable' inside diffusers.
        # To bypass (panel 1 / single-panel), pass a black dummy at scale 0.0.
        _black = Image.new("RGB", (settings.SD_WIDTH, settings.SD_HEIGHT), (0, 0, 0))
        ip_kwargs = {}
        if self.ip_adapter_loaded and hasattr(self.pipeline, "set_ip_adapter_scale"):
            use_reference = panel_index > 0 and self.ip_reference_image is not None
            if use_reference:
                ip_kwargs["ip_adapter_image"] = self.ip_reference_image
                # Dynamic scale — lower for action/combat (avoids identity bleed)
                is_action = should_use_pose(action or positive_prompt)
                combat_keywords = ["enemy", "beast", "monster", "dragon", "creature", "demon"]
                has_combat = any(kw in positive_prompt.lower() for kw in combat_keywords)
                ip_scale = 0.75 if (is_action or has_combat) else 0.80
            else:
                # Panel 1 or no reference yet — bypass adapter, character forms freely
                ip_kwargs["ip_adapter_image"] = _black
                ip_scale = 0.0
            self.pipeline.set_ip_adapter_scale(ip_scale)
            
            # [CharacterConsistency] log line matching requirements exactly
            total = panel_count if panel_count else (panel_index + 1)
            print(f"[CharacterConsistency] Panel {panel_index + 1}/{total} — IP scale: {ip_scale:.2f}")

        # --- Dynamic Pose Selection Mapping ---
        if panel_count is None or panel_count <= 1:
            # Single panel or invalid count -> first panel -> UPRIGHT_STANDING
            pose_id = 0
        elif panel_index == 0:
            pose_id = 0
        elif panel_index == panel_count - 1:
            pose_id = 3
        else:
            # Middle panels: panel_index % 6 biased by layout_type
            base_pose = panel_index % 6
            if layout_type:
                layout_lower = layout_type.lower()
                panel_rng = random.Random(seed + panel_index)
                if panel_rng.random() < 0.6:
                    if "action" in layout_lower:
                        pose_id = panel_rng.choice([2, 5])
                    elif "drama" in layout_lower:
                        pose_id = panel_rng.choice([1, 4])
                    elif "dialog" in layout_lower or "talk" in layout_lower:
                        pose_id = panel_rng.choice([6, 1])
                    else:
                        pose_id = base_pose
                else:
                    pose_id = base_pose
            else:
                pose_id = base_pose

        # --- Draw pose skeleton based on dynamic selection ---
        pose_image = self.pose_library.get_pose_image(pose_id)

        # --- Prompt embeds -----------------------------------------------
        p_embeds, n_embeds = self.get_prompt_embeds(positive_prompt, negative_prompt)

        # --- Inference ---------------------------------------------------
        common = dict(
            prompt_embeds=p_embeds,
            negative_prompt_embeds=n_embeds,
            generator=generator,
            num_inference_steps=settings.SD_INFERENCE_STEPS,
            guidance_scale=settings.SD_GUIDANCE_SCALE,
            width=settings.SD_WIDTH,
            height=settings.SD_HEIGHT,
            **ip_kwargs,
        )

        try:
            if self.controlnet_enabled:
                image = self.pipeline(
                    **common,
                    image=pose_image,
                    controlnet_conditioning_scale=getattr(
                        settings, "SD_CONTROLNET_CONDITIONING_SCALE", 0.70
                    ),
                ).images[0]
            else:
                image = self.pipeline(**common).images[0]
        except Exception as exc:
            print(f"[SD] Generation failed: {exc}")
            raise

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        image.save(output_path)
        return output_path
