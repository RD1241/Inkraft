import os
import json
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from config import settings
from core.memory_manager import MemoryManager
from core.prompt_builder import PromptBuilder
from core.comic_renderer import ComicRenderer
from core.job_manager import JobManager
from core.cache_manager import CacheManager
from core.monitoring import DriftMonitor

from core.storyboard_director import StoryboardDirector
from core.expression_engine import ExpressionEngine
from core.camera_director import CameraDirector

from providers.factory import get_llm_provider, get_image_provider, get_storage_provider

class ComicService:
    def __init__(self):
        self.memory_manager = MemoryManager()
        self.comic_renderer = ComicRenderer()
        self.job_manager = JobManager()
        self.cache_manager = CacheManager()
        self.drift_monitor = DriftMonitor()
        
        # Stage 2 planners & directors
        self.storyboard_director = StoryboardDirector()
        self.expression_engine = ExpressionEngine()
        self.camera_director = CameraDirector()
        
        # Generation is API-bound (fal.ai), not GPU-bound — safe for concurrent users.
        # Env-configurable (settings.CONCURRENT_WORKERS, default 4) for open-beta scaling.
        self.job_executor = ThreadPoolExecutor(max_workers=getattr(settings, "CONCURRENT_WORKERS", 4))

    def queue_comic_generation(self, text: str, style: str, panel_count: int = None, layout_type: str = None, user_id: str = None, characters: list = None, generation_format: str = None, color_mode: str = "auto") -> tuple[str, bool]:
        """
        Queues a new job or returns a cached result.
        
        Returns:
            tuple[str, bool]: (job_id, cached)
        """
        text = text.strip()

        # Determine panel_count_mode
        if panel_count is not None:
            panel_count_mode = "user_specified"
        elif layout_type is not None:
            panel_count_mode = "layout_type"
        else:
            panel_count_mode = "ai_decided"

        # Cache check
        if getattr(settings, "ENABLE_CACHING", True):
            cached = self.cache_manager.get_cached_result(text)
            if cached:
                job_id = self.job_manager.create_job(
                    panel_count=panel_count,
                    layout_type=layout_type,
                    panel_count_mode=panel_count_mode,
                    generation_format=generation_format,
                    user_id=user_id
                )
                self.job_manager.update_job(job_id, status="completed", result=json.dumps(cached))
                
                # Auto-save cached sheet under user account
                try:
                    from services.history_service import history_service
                    title = history_service.auto_title(text)
                    history_service.save_comic(
                        user_id=user_id or "00000000-0000-0000-0000-000000000000",
                        job_id=job_id,
                        title=title,
                        style=style,
                        layout_type=layout_type or "standard",
                        panel_count=cached.get("total_scenes") or len(cached.get("panels", [])),
                        panel_count_mode=panel_count_mode,
                        panel_urls=cached.get("panels", []),
                        final_page=cached.get("final_page")
                    )
                except Exception as save_err:
                    print(f"[Warning] Failed to save cached comic to history: {save_err}")
                
                return job_id, True

        # Queue new job
        job_id = self.job_manager.create_job(
            panel_count=panel_count,
            layout_type=layout_type,
            panel_count_mode=panel_count_mode,
            generation_format=generation_format,
            user_id=user_id
        )
        self.job_executor.submit(self.process_job_worker, job_id, text, style, panel_count, layout_type, user_id, characters, generation_format, color_mode)
        return job_id, False

    def process_job_worker(self, job_id: str, text: str, style: str = "anime", panel_count: int = None, layout_type: str = None, user_id: str = None, characters: list = None, generation_format: str = None, color_mode: str = "auto"):
        """Background worker that handles the heavy AI generation pipeline."""
        start_time = time.time()
        dominant_char = None
        
        # Instantiate active providers dynamically for this job
        llm_provider = get_llm_provider()
        image_provider = get_image_provider()
        storage_provider = get_storage_provider()
        
        try:
            resolved_format = self.resolve_generation_format(style, generation_format, panel_count)
            
            if resolved_format == "single_page":
                # Step 0: Clear memory
                self.job_manager.update_job(job_id, status="processing", progress="0% - Analyzing your story...")
                self.memory_manager.clear_memory()
                self.memory_manager.load_character_design_sheets(user_id, request_sheets=characters)

                # Step 1: LLM scene extraction
                self.job_manager.update_job(job_id, status="processing", progress="20% - Extracting the key scene...")
                scene_data = llm_provider.process_text(text, panel_count=1, layout_type=layout_type)
                if not scene_data.get("scenes"):
                    raise ValueError("Failed to extract scenes from text.")

                # Step 1.5: Storyboard planning
                self.job_manager.update_job(job_id, status="processing", progress="35% - Planning your cinematic panel...")
                storyboard_plan = self.storyboard_director.plan(scene_data, panel_count=1, layout_type=layout_type)
                
                # Pick the highest-tension panel if multiple returned
                if storyboard_plan.panels:
                    if len(storyboard_plan.panels) > 1:
                        single_panel = max(storyboard_plan.panels, key=lambda p: p.tension_level)
                    else:
                        single_panel = storyboard_plan.panels[0]
                else:
                    raise ValueError("Storyboard plan returned no panels.")

                # Align panel fields into standard scene dictionary for PromptBuilder and memory
                characters_list = []
                for s in scene_data.get("scenes", []):
                    if s.get("scene_id") == single_panel.scene_id:
                        characters_list = s.get("characters", [])
                        break
                if not characters_list and scene_data.get("scenes"):
                    characters_list = scene_data["scenes"][0].get("characters", [])

                # Filter characters_list if it is a single-character close-up
                if single_panel.camera_shot in ("CLOSE_UP", "EXTREME_CLOSE_UP") and single_panel.focus_character:
                    focus_name_lower = str(single_panel.focus_character).strip().lower()
                    filtered_chars = [c for c in characters_list if c.get("name", "").strip().lower() == focus_name_lower]
                    if filtered_chars:
                        characters_list = filtered_chars

                panel_scene = {
                    "scene_id": single_panel.scene_id,
                    "panel_id": single_panel.panel_id,
                    "focus_character": single_panel.focus_character,
                    "action": single_panel.action,
                    "dialogue": single_panel.dialogue,
                    "camera": self.camera_director.get_shot_tokens(single_panel.camera_shot),
                    "emotion": self.expression_engine.build_emotion_prompt_segment(single_panel.emotion),
                    "lighting": single_panel.lighting,
                    "environment": storyboard_plan.global_environment,
                    "global_environment": storyboard_plan.global_environment,
                    "characters": characters_list
                }
                self.memory_manager.process_scene_characters(panel_scene, story_text=text)

                # Step 2: Image Generation
                self.job_manager.update_job(job_id, status="processing", progress="65% - Generating your page...")

                style_prompt_builder = PromptBuilder(style=style)
                pos_prompt, neg_prompt = style_prompt_builder.build_prompt(
                    panel_scene, self.memory_manager, is_continuation=False, style=style, color_mode=color_mode
                )

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                job_output_dir = storage_provider.get_job_directory(timestamp)
                image_filename = f"scene_{single_panel.panel_id}.png"
                image_path = os.path.join(job_output_dir, image_filename)

                # Determine secondary character name (matching draw_panel)
                secondary_char = ""
                if single_panel.focus_character and characters_list:
                    focus_name_lower = str(single_panel.focus_character).strip().lower()
                    for char in characters_list:
                        cname = char.get("name", "")
                        if cname and cname.strip().lower() != focus_name_lower:
                            secondary_char = cname
                            break
                if not secondary_char and len(characters_list) >= 2:
                    secondary_char = characters_list[1].get("name", "")

                scene_seed = settings.SD_DEFAULT_SEED
                image_provider.generate_image(
                    positive_prompt=pos_prompt,
                    negative_prompt=neg_prompt,
                    output_path=image_path,
                    seed=scene_seed,
                    reference_image_path=None,
                    reference_strength=None,
                    base_latents=None,
                    scene_id=single_panel.scene_id,
                    panel_index=0,
                    style=style,
                    action=single_panel.action,
                    panel_count=1,
                    layout_type=layout_type,
                    panel_width=1024,
                    panel_height=1450,
                    focus_character=single_panel.focus_character,
                    secondary_character=secondary_char,
                    job_id=job_id,
                    color_mode=color_mode,
                )

                # Lock character anchor if dominant character exists
                dominant_char = self.memory_manager.consistency.get_dominant_character(panel_scene)
                if dominant_char:
                    character_reference_path = os.path.join(job_output_dir, f"{dominant_char.lower()}_ref.png")
                    try:
                        image_provider.extract_character_anchor(image_path, character_reference_path)
                        self.memory_manager.consistency.lock_character_anchor(dominant_char, character_reference_path)
                    except Exception as e:
                        print(f"[Warning] Character anchor extraction failed for {dominant_char}: {e}")

                # Draw action sound effect on the image if style == "manga" and tension_level >= 7
                if style.lower() == "manga" and single_panel.tension_level >= 7:
                    try:
                        self.comic_renderer.draw_speech_bubble(
                            image_path=image_path,
                            dialogues=[],
                            output_path=image_path,
                            panel_index=single_panel.panel_id,
                            style=style,
                            layout_type="action",
                            tension_level=single_panel.tension_level,
                            action_description=single_panel.action,
                            total_panels=1
                        )
                    except Exception as e:
                        print(f"[Warning] Sound effect rendering failed for single page: {e}")

                # Step 3: Single Page rendering
                self.job_manager.update_job(job_id, status="processing", progress="90% - Adding finishing touches...")

                # Concatenate dialogue and narration texts
                speech_texts = []
                narration_texts = []
                for d in single_panel.dialogue:
                    d_type = str(d.get("type", "speech")).lower()
                    d_speaker = str(d.get("speaker", "")).lower()
                    d_text = str(d.get("text", "")).strip()
                    if not d_text:
                        continue
                    if d_type == "narration" or d_speaker == "narrator":
                        narration_texts.append(d_text)
                    else:
                        speech_texts.append(d_text)

                single_panel_dialogue = " ".join(speech_texts)
                single_panel_narration = " ".join(narration_texts)

                from PIL import Image
                panel_image_obj = Image.open(image_path)
                final_page_filename = "final_comic_page.png"
                final_page_path = os.path.join(job_output_dir, final_page_filename)

                final_page_img = self.comic_renderer.create_single_page(
                    image=panel_image_obj,
                    dialogue=single_panel_dialogue,
                    narration=single_panel_narration,
                    style=style,
                    watermark=True
                )
                final_page_img.save(final_page_path)

                # Save metadata
                try:
                    single_storyboard_data = storyboard_plan.to_dict()
                    single_storyboard_data["panels"] = [single_panel.to_dict()]
                    single_storyboard_data["total_panels"] = 1
                    with open(os.path.join(job_output_dir, "metadata.json"), "w") as f:
                        json.dump(single_storyboard_data, f, indent=4)
                except Exception:
                    pass

                # Step 4: Cleanup
                try:
                    image_provider.unload_model()
                except Exception as e:
                    print(f"[Warning] Model unload failed: {e}")

                # Step 5: Save result and cache
                web_panels = [storage_provider.get_web_url(timestamp, os.path.basename(image_path))]
                web_final = storage_provider.get_web_url(timestamp, final_page_filename)

                result_payload = {
                    "message": "Comic generated successfully!",
                    "total_scenes": 1,
                    "final_page": web_final,
                    "panels": web_panels,
                    "scenes": [single_panel.to_dict()],
                }

                gen_time = time.time() - start_time
                self.drift_monitor.log_job_metrics(job_id, text, [single_panel.to_dict()], gen_time, True, [image_path])
                self.cache_manager.set_cached_result(text, result_payload)
                self.job_manager.update_job(job_id, status="completed", progress="100% - Your page is ready!", result=json.dumps(result_payload))

                # Auto-save history
                try:
                    from services.history_service import history_service
                    title = history_service.auto_title(text)
                    history_service.save_comic(
                        user_id=user_id or "00000000-0000-0000-0000-000000000000",
                        job_id=job_id,
                        title=title,
                        style=style,
                        layout_type=layout_type or "standard",
                        panel_count=1,
                        panel_count_mode="ai_decided",
                        panel_urls=web_panels,
                        final_page=web_final
                    )
                except Exception as save_err:
                    print(f"[Warning] Failed to auto-save comic to history: {save_err}")

                # Log success metadata for single_page (Phase 5 Fix)
                try:
                    gen_seed = settings.SD_DEFAULT_SEED
                    if hasattr(image_provider, "character_seeds") and image_provider.character_seeds:
                        first_val = list(image_provider.character_seeds.values())
                        if first_val:
                            gen_seed = first_val[0]
                    
                    ref_path = None
                    if dominant_char:
                        ref_path = os.path.join(job_output_dir, f"{dominant_char.lower()}_ref.png")
                    
                    # Retrieve and aggregate panel metrics
                    job_metrics = []
                    if hasattr(image_provider, "get_and_clear_job_metrics"):
                        job_metrics = image_provider.get_and_clear_job_metrics(job_id)
                    
                    total_submissions = sum(m.get("actual_submissions", 1) for m in job_metrics)
                    all_request_ids = []
                    for m in job_metrics:
                        all_request_ids.extend(m.get("actual_request_ids", []))
                    total_safety_retries = sum(m.get("actual_safety_retries", 0) for m in job_metrics)
                    total_network_retries = sum(m.get("actual_network_retries", 0) for m in job_metrics)
                    total_reroutes = sum(m.get("actual_reroutes", 0) for m in job_metrics)
                    total_cost = sum(m.get("estimated_request_cost", 0.0025) for m in job_metrics)
                    
                    endpoints = list(set(m.get("actual_endpoint", "unknown") for m in job_metrics))
                    models = list(set(m.get("actual_model", "unknown") for m in job_metrics))
                    
                    actual_endpoint = endpoints[0] if len(endpoints) == 1 else ",".join(endpoints) if endpoints else "unknown"
                    actual_model = models[0] if len(models) == 1 else ",".join(models) if models else "unknown"
                    
                    self._log_generation_metadata(
                        timestamp=datetime.now().isoformat(),
                        style=style,
                        seed=gen_seed,
                        characters=list(self.active_sheets.keys()) if hasattr(self, "active_sheets") else [dominant_char] if dominant_char else [],
                        reference_path=ref_path,
                        retry_count=0,
                        duration_seconds=gen_time,
                        safety_triggered=(total_safety_retries > 0 or total_reroutes > 0),
                        status="success",
                        credit_txn="deducted_1",
                        user_id=user_id,
                        panel_count=1,
                        actual_submissions=total_submissions,
                        actual_request_ids=all_request_ids,
                        actual_safety_retries=total_safety_retries,
                        actual_network_retries=total_network_retries,
                        actual_reroutes=total_reroutes,
                        actual_endpoint=actual_endpoint,
                        actual_model=actual_model,
                        generation_duration=int(gen_time),
                        estimated_request_cost=total_cost
                    )
                except Exception as log_err:
                    print(f"[Warning] Failed to log single page success metadata: {log_err}")

                return

            self.job_manager.update_job(job_id, status="processing")
            self.memory_manager.clear_memory()
            self.memory_manager.load_character_design_sheets(user_id, request_sheets=characters)

            # Step 1: LLM scene extraction
            self.job_manager.update_job(job_id, status="processing", progress="Extracting scenes with LLM...")
            scene_data = llm_provider.process_text(text, panel_count=panel_count, layout_type=layout_type)
            if not scene_data.get("scenes"):
                raise ValueError("Failed to extract scenes from text.")

            # Step 1.5: Storyboard planning BEFORE image generation starts [NEW - 2C]
            # StoryboardDirector plans the visual sequence and locks cinematic elements
            self.job_manager.update_job(job_id, status="processing", progress="Planning storyboard layout...")
            storyboard_plan = self.storyboard_director.plan(scene_data, panel_count=panel_count, layout_type=layout_type)
            total_panels = storyboard_plan.total_panels
            
            # Map the plan into scene_data to preserve all calculated metrics in metadata.json
            original_scene_data = scene_data
            scene_data = storyboard_plan.to_dict()
            scene_data["scenes"] = original_scene_data.get("scenes", [])

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            job_output_dir = storage_provider.get_job_directory(timestamp)

            # Build a prompt_builder keyed to the detected style
            style_prompt_builder = PromptBuilder(style=style)

            output_images = []
            global_env = storyboard_plan.global_environment
            scene_seed = settings.SD_DEFAULT_SEED
            base_latents = image_provider.create_base_latents(scene_seed)

            # Step 1.6: Calculate page layout BEFORE generating panel images to know their exact dimensions (Fix 1)
            from core.panel_compositor import PanelCompositor
            compositor = PanelCompositor()
            layout_type_val = scene_data.get("layout_type") or "standard"
            page_layout = compositor.calculate_layout(storyboard_plan.panels, layout_type=layout_type_val)

            # Step 1.7: Pre-process character profiles sequentially to avoid SQLite concurrent write contention (Fix 3)
            for i, panel in enumerate(storyboard_plan.panels):
                characters_list = []
                for s in scene_data.get("scenes", []):
                    if s.get("scene_id") == panel.scene_id:
                        characters_list = s.get("characters", [])
                        break
                panel_scene = {
                    "scene_id": panel.scene_id,
                    "panel_id": panel.panel_id,
                    "focus_character": panel.focus_character,
                    "action": panel.action,
                    "dialogue": panel.dialogue,
                    "camera": self.camera_director.get_shot_tokens(panel.camera_shot),
                    "emotion": self.expression_engine.build_emotion_prompt_segment(panel.emotion),
                    "lighting": panel.lighting,
                    "environment": global_env,
                    "global_environment": global_env,
                    "characters": characters_list
                }
                self.memory_manager.process_scene_characters(panel_scene, story_text=text)

            output_images_dict = {}
            first_panel_pos_prompt = ""
            import threading
            job_update_lock = threading.Lock()

            def draw_panel(i, panel):
                panel_num = i + 1
                
                # Get layout dimensions for this panel
                panel_width = 768
                panel_height = 1024
                for pc in page_layout.panels:
                    if pc.panel_id == panel.panel_id:
                        panel_width = pc.width
                        panel_height = pc.height
                        break

                # Get characters from original extracted scene matching this scene_id
                characters_list = []
                scene_plan_scenes = scene_data.get("scenes", [])
                orig_scene = None
                for s in scene_plan_scenes:
                    if s.get("scene_id") == panel.scene_id:
                        orig_scene = s
                        break
                if not orig_scene and scene_plan_scenes:
                    orig_scene = scene_plan_scenes[0]
                
                if orig_scene:
                    characters_list = orig_scene.get("characters", [])

                # Determine the secondary character name
                secondary_char = ""
                if panel.focus_character and characters_list:
                    focus_name_lower = str(panel.focus_character).strip().lower()
                    for char in characters_list:
                        cname = char.get("name", "")
                        if cname and cname.strip().lower() != focus_name_lower:
                            secondary_char = cname
                            break
                if not secondary_char and len(characters_list) >= 2:
                    secondary_char = characters_list[1].get("name", "")

                # Filter characters_list if it is a single-character close-up
                if panel.camera_shot in ("CLOSE_UP", "EXTREME_CLOSE_UP") and panel.focus_character:
                    focus_name_lower = str(panel.focus_character).strip().lower()
                    filtered_chars = [c for c in characters_list if c.get("name", "").strip().lower() == focus_name_lower]
                    if filtered_chars:
                        characters_list = filtered_chars
                        secondary_char = ""

                # Align panel fields into a standard scene dictionary for the prompt builder
                panel_scene = {
                    "scene_id": panel.scene_id,
                    "panel_id": panel.panel_id,
                    "focus_character": panel.focus_character,
                    "action": panel.action,
                    "dialogue": panel.dialogue,
                    "camera": self.camera_director.get_shot_tokens(panel.camera_shot),
                    "emotion": self.expression_engine.build_emotion_prompt_segment(panel.emotion),
                    "lighting": panel.lighting,
                    "environment": global_env,
                    "global_environment": global_env,
                    "characters": characters_list
                }

                # Get dominant character for IP-Adapter consistency locks
                dominant_char = self.memory_manager.consistency.get_dominant_character(panel_scene)
                
                use_reference = False
                character_reference_path = None
                if i > 0 and dominant_char:
                    ref_img = self.memory_manager.consistency.get_ip_adapter_reference(dominant_char, panel_index=i)
                    if ref_img and os.path.exists(ref_img):
                        character_reference_path = ref_img
                        use_reference = True

                # Private prompt builder to ensure thread safety
                thread_prompt_builder = PromptBuilder(style=style)
                if i > 0 and first_panel_pos_prompt:
                    thread_prompt_builder.last_positive_prompt = first_panel_pos_prompt

                # Build prompt using multi-layered PromptBuilder V2
                pos_prompt, neg_prompt = thread_prompt_builder.build_prompt(
                    panel_scene, self.memory_manager, is_continuation=(i > 0), style=style, color_mode=color_mode
                )

                if use_reference:
                    pos_prompt, neg_prompt = thread_prompt_builder.apply_reference_conditioning_prompt(pos_prompt, neg_prompt)

                image_filename = f"scene_{panel.panel_id}.png"
                image_path = os.path.join(job_output_dir, image_filename)

                # Retry loop for image generation
                success = False
                last_error = None
                for attempt in range(settings.MAX_RETRIES):
                    try:
                        image_provider.generate_image(
                            positive_prompt=pos_prompt,
                            negative_prompt=neg_prompt,
                            output_path=image_path,
                            seed=scene_seed + i,
                            reference_image_path=character_reference_path if use_reference else None,
                            reference_strength=settings.SD_REFERENCE_STRENGTH if use_reference else None,
                            base_latents=base_latents,
                            scene_id=panel.scene_id,
                            panel_index=i,
                            style=style,
                            action=panel.action,
                            panel_count=total_panels,
                            layout_type=layout_type,
                            panel_width=panel_width,
                            panel_height=panel_height,
                            focus_character=panel.focus_character,
                            secondary_character=secondary_char,
                            job_id=job_id,
                            color_mode=color_mode,
                        )
                        success = True
                        break
                    except Exception as e:
                        last_error = str(e)
                        print(f"[Warning] Panel {panel_num} attempt {attempt + 1} failed: {e}")
                        # Simplify prompt on retry
                        pos_prompt = pos_prompt.split(",")[0] + ", " + settings.MASTER_STYLE_TAG

                if not success:
                    print(f"[Error] Panel {panel_num} failed generation after {settings.MAX_RETRIES} attempts.")
                    raise RuntimeError(f"Panel {panel_num} failed generation: {last_error}")

                # Lock character anchor after Panel 1 generation is complete
                if i == 0 and dominant_char:
                    character_reference_path = os.path.join(job_output_dir, f"{dominant_char.lower()}_ref.png")
                    try:
                        image_provider.extract_character_anchor(image_path, character_reference_path)
                        self.memory_manager.consistency.lock_character_anchor(dominant_char, character_reference_path)
                    except Exception as e:
                        print(f"[Warning] Character anchor extraction failed for {dominant_char}: {e}")
                        character_reference_path = None

                # Draw speech bubbles and SFX (Fix 3)
                if panel.dialogue or (layout_type_val and layout_type_val.lower() == "action" and panel.tension_level >= 7):
                    try:
                        self.comic_renderer.draw_speech_bubble(
                            image_path=image_path,
                            dialogues=panel.dialogue,
                            output_path=image_path,
                            panel_index=panel.panel_id,
                            style=style if style else "manga",
                            layout_type=layout_type_val if layout_type_val else "action",
                            tension_level=panel.tension_level if hasattr(panel, "tension_level") and panel.tension_level is not None else 5,
                            action_description=panel.action if hasattr(panel, "action") and panel.action is not None else "",
                            total_panels=total_panels
                        )
                    except Exception as e:
                        print(f"[Warning] Speech bubble or SFX failed for panel {panel_num}: {e}")

                return image_path, pos_prompt

            # Determine dynamic style-aware time estimate
            style_lower = (style or "anime").lower().strip()
            est = "~1m"
            if style_lower == "cinematic":
                est = "~1-2m"
            elif style_lower == "realistic":
                est = "~4-8m"

            # Step 2.1: Generate Panel 1 (index 0) synchronously (Fix 3 - Step 3)
            self.job_manager.update_job(
                job_id, status="processing",
                progress=f"Drawing panel 1... ({est})"
            )
            first_panel = storyboard_plan.panels[0]
            first_panel_path, first_panel_pos_prompt = draw_panel(0, first_panel)
            output_images_dict[first_panel.panel_id] = first_panel_path

            # Step 2.2: Generate Panels 2+ in parallel (Fix 3 - Step 3)
            if total_panels > 1:
                with job_update_lock:
                    self.job_manager.update_job(
                        job_id, status="processing",
                        progress=f"Drawing panels 2-{total_panels} in parallel... ({est})"
                    )

                remaining_panels = storyboard_plan.panels[1:]
                completed_count = 0
                total_remaining = len(remaining_panels)

                def run_parallel_panel(idx, panel):
                    nonlocal completed_count
                    try:
                        path, _ = draw_panel(idx, panel)
                    except Exception as e:
                        print(f"[Error] Thread exception for panel {panel.panel_id}: {e}")
                        raise e

                    with job_update_lock:
                        completed_count += 1
                        self.job_manager.update_job(
                            job_id, status="processing",
                            progress=f"Drawing panels 2-{total_panels} in parallel... ({completed_count}/{total_remaining} completed)"
                        )
                    return panel.panel_id, path

                with ThreadPoolExecutor(max_workers=total_remaining) as executor:
                    futures = [executor.submit(run_parallel_panel, i, panel) for i, panel in enumerate(remaining_panels, start=1)]
                    for future in futures:
                        pid, path = future.result()
                        output_images_dict[pid] = path

            # Re-assemble output_images list in correct order
            output_images = [output_images_dict[p.panel_id] for p in storyboard_plan.panels if p.panel_id in output_images_dict]

            # Step 3: Assemble comic page using variable panel layout compositor [NEW - 2D]
            self.job_manager.update_job(job_id, status="processing", progress="Assembling final comic page...")
            final_page_filename = "final_comic_page.png"
            final_page_path = os.path.join(job_output_dir, final_page_filename)
            
            # Save metadata before rendering so ComicRenderer can parse the storyboard json for dynamic coordinates
            try:
                with open(os.path.join(job_output_dir, "metadata.json"), "w") as f:
                    json.dump(scene_data, f, indent=4)
            except Exception:
                pass

            # Render page - automatically calculates coordinates and places panels elegantly
            self.comic_renderer.create_comic_page(output_images, final_page_path)

            # Step 4: Cleanup memory — unload model to free resources
            try:
                image_provider.unload_model()
            except Exception as e:
                print(f"[Warning] Model unload failed: {e}")

            # Step 5: Build result and cache using StorageProvider URLs
            web_panels = [storage_provider.get_web_url(timestamp, os.path.basename(p)) for p in output_images]
            web_final = storage_provider.get_web_url(timestamp, final_page_filename)

            result_payload = {
                "message": "Comic generated successfully!",
                "total_scenes": total_panels,
                "final_page": web_final,
                "panels": web_panels,
                "scenes": scene_data["panels"],
            }

            gen_time = time.time() - start_time
            self.drift_monitor.log_job_metrics(job_id, text, scene_data["panels"], gen_time, True, output_images)
            self.cache_manager.set_cached_result(text, result_payload)
            self.job_manager.update_job(job_id, status="completed", result=json.dumps(result_payload))

            # Auto-save sheet under user account upon completion
            try:
                from services.history_service import history_service
                title = history_service.auto_title(text)
                if panel_count is not None:
                    panel_count_mode = "user_specified"
                elif layout_type is not None:
                    panel_count_mode = "layout_type"
                else:
                    panel_count_mode = "ai_decided"
                history_service.save_comic(
                    user_id=user_id or "00000000-0000-0000-0000-000000000000",
                    job_id=job_id,
                    title=title,
                    style=style,
                    layout_type=layout_type or "standard",
                    panel_count=total_panels,
                    panel_count_mode=panel_count_mode,
                    panel_urls=web_panels,
                    final_page=web_final
                )
            except Exception as save_err:
                print(f"[Warning] Failed to auto-save comic to history: {save_err}")

            # Log success metadata
            try:
                gen_seed = settings.SD_DEFAULT_SEED
                if hasattr(image_provider, "character_seeds") and image_provider.character_seeds:
                    first_val = list(image_provider.character_seeds.values())
                    if first_val:
                        gen_seed = first_val[0]
                
                ref_path = None
                if dominant_char:
                    ref_path = os.path.join(job_output_dir, f"{dominant_char.lower()}_ref.png")
                
                # Retrieve and aggregate panel metrics (Amendment 3)
                job_metrics = []
                if hasattr(image_provider, "get_and_clear_job_metrics"):
                    job_metrics = image_provider.get_and_clear_job_metrics(job_id)
                
                total_submissions = sum(m.get("actual_submissions", 1) for m in job_metrics)
                all_request_ids = []
                for m in job_metrics:
                    all_request_ids.extend(m.get("actual_request_ids", []))
                total_safety_retries = sum(m.get("actual_safety_retries", 0) for m in job_metrics)
                total_network_retries = sum(m.get("actual_network_retries", 0) for m in job_metrics)
                total_reroutes = sum(m.get("actual_reroutes", 0) for m in job_metrics)
                total_cost = sum(m.get("estimated_request_cost", 0.0025) for m in job_metrics)
                
                endpoints = list(set(m.get("actual_endpoint", "unknown") for m in job_metrics))
                models = list(set(m.get("actual_model", "unknown") for m in job_metrics))
                
                actual_endpoint = endpoints[0] if len(endpoints) == 1 else ",".join(endpoints) if endpoints else "unknown"
                actual_model = models[0] if len(models) == 1 else ",".join(models) if models else "unknown"
                
                job_duration = time.time() - start_time
                
                self._log_generation_metadata(
                    timestamp=datetime.now().isoformat(),
                    style=style,
                    seed=gen_seed,
                    characters=list(self.active_sheets.keys()) if hasattr(self, "active_sheets") else [dominant_char] if dominant_char else [],
                    reference_path=ref_path,
                    retry_count=0,
                    duration_seconds=job_duration,
                    safety_triggered=(total_safety_retries > 0 or total_reroutes > 0),
                    status="success",
                    credit_txn="deducted_1",
                    user_id=user_id,
                    panel_count=total_panels,
                    actual_submissions=total_submissions,
                    actual_request_ids=all_request_ids,
                    actual_safety_retries=total_safety_retries,
                    actual_network_retries=total_network_retries,
                    actual_reroutes=total_reroutes,
                    actual_endpoint=actual_endpoint,
                    actual_model=actual_model,
                    generation_duration=int(job_duration),
                    estimated_request_cost=total_cost
                )
            except Exception as log_err:
                print(f"[Warning] Failed to log success metadata: {log_err}")

        except Exception as e:
            gen_time = time.time() - start_time
            print(f"[Error] Job {job_id} failed: {e}")
            self.drift_monitor.log_job_metrics(job_id, text, [], gen_time, False, [])
            self.job_manager.update_job(job_id, status="failed", error=str(e))
            
            # Refund credit on generation failure — refund the SAME amount that was
            # charged (tiered by panel_count), so a failed N-credit comic returns N.
            if user_id:
                try:
                    from services.credits_service import credits_service
                    refund_amount = credits_service.credits_for_panels(panel_count)
                    credits_service.refund_credit(user_id, amount=refund_amount)
                    print(f"[CreditsService] Refunded {refund_amount} credit(s) to user {user_id} due to generation failure.")
                except Exception as refund_err:
                    print(f"[Error] Failed to refund credit to user {user_id}: {refund_err}")

            # Log failed metadata
            try:
                # Retrieve metrics even on failure
                job_metrics = []
                if hasattr(image_provider, "get_and_clear_job_metrics"):
                    job_metrics = image_provider.get_and_clear_job_metrics(job_id)
                
                total_submissions = sum(m.get("actual_submissions", 1) for m in job_metrics)
                all_request_ids = []
                for m in job_metrics:
                    all_request_ids.extend(m.get("actual_request_ids", []))
                total_safety_retries = sum(m.get("actual_safety_retries", 0) for m in job_metrics)
                total_network_retries = sum(m.get("actual_network_retries", 0) for m in job_metrics)
                total_reroutes = sum(m.get("actual_reroutes", 0) for m in job_metrics)
                total_cost = sum(m.get("estimated_request_cost", 0.0025) for m in job_metrics)
                
                endpoints = list(set(m.get("actual_endpoint", "unknown") for m in job_metrics))
                models = list(set(m.get("actual_model", "unknown") for m in job_metrics))
                
                actual_endpoint = endpoints[0] if len(endpoints) == 1 else ",".join(endpoints) if endpoints else "unknown"
                actual_model = models[0] if len(models) == 1 else ",".join(models) if models else "unknown"
                
                self._log_generation_metadata(
                    timestamp=datetime.now().isoformat(),
                    style=style,
                    seed=settings.SD_DEFAULT_SEED,
                    characters=[],
                    reference_path=None,
                    retry_count=0,
                    duration_seconds=gen_time,
                    safety_triggered=("Safety filter" in str(e) or total_safety_retries > 0 or total_reroutes > 0),
                    status="failed",
                    credit_txn="refunded_1" if user_id else "none",
                    user_id=user_id,
                    panel_count=panel_count,
                    actual_submissions=total_submissions,
                    actual_request_ids=all_request_ids,
                    actual_safety_retries=total_safety_retries,
                    actual_network_retries=total_network_retries,
                    actual_reroutes=total_reroutes,
                    actual_endpoint=actual_endpoint,
                    actual_model=actual_model,
                    generation_duration=int(gen_time),
                    estimated_request_cost=total_cost
                )
            except Exception as log_err:
                print(f"[Warning] Failed to log failure metadata: {log_err}")

            # Always free VRAM on failure
            try:
                image_provider.unload_model()
            except Exception:
                pass

    def _log_generation_metadata(
        self,
        timestamp: str,
        style: str,
        seed: int,
        characters: list,
        reference_path: str,
        retry_count: int,
        duration_seconds: float,
        safety_triggered: bool,
        status: str,
        credit_txn: str = "deducted_1",
        user_id: str = None,
        panel_count: int = None,
        actual_submissions: int = 1,
        actual_request_ids: list = None,
        actual_safety_retries: int = 0,
        actual_network_retries: int = 0,
        actual_reroutes: int = 0,
        actual_endpoint: str = "unknown",
        actual_model: str = "unknown",
        generation_duration: int = None,
        estimated_request_cost: float = 0.0025
    ):
        try:
            log_dir = getattr(settings, "LOGS_DIR", os.path.join(settings.BASE_DIR, "logs"))
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, "generation_metadata.jsonl")
            
            from providers.image.fal_ai import STYLE_MODEL_MAP
            model_info = STYLE_MODEL_MAP.get(style.lower(), {})
            fallback_model = model_info.get("model_name", model_info.get("endpoint", "unknown"))

            log_entry = {
                "timestamp": timestamp,
                "user_id": user_id,
                "panel_count": panel_count,
                "style": style,
                "model": actual_model if actual_model != "unknown" else fallback_model,
                "seed": seed,
                "characters": characters,
                "reference_path": reference_path,
                "retry_count": retry_count,
                "duration_seconds": int(duration_seconds),
                "safety_triggered": safety_triggered,
                "status": status,
                "credit_transaction_result": credit_txn,
                
                # New Cost Tracking V2 fields (Amendment 3)
                "actual_submissions": actual_submissions,
                "actual_request_ids": actual_request_ids or [],
                "actual_safety_retries": actual_safety_retries,
                "actual_network_retries": actual_network_retries,
                "actual_reroutes": actual_reroutes,
                "actual_endpoint": actual_endpoint,
                "actual_model": actual_model,
                "generation_duration": generation_duration if generation_duration is not None else int(duration_seconds),
                "estimated_request_cost": estimated_request_cost
            }
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            print(f"[Warning] Failed to write generation metadata: {e}")

    def resolve_generation_format(self, style: str, generation_format: str = None, panel_count: int = None) -> str:
        style_norm = (style or "").strip().lower()
        if generation_format == "single_page":
            return "single_page"
        if generation_format == "panel_strip":
            return "panel_strip"
        # An explicit multi-panel request wins for any style except the inherently
        # single-page webtoon styles (manhwa/manhua render as one tall page).
        if panel_count is not None and panel_count > 1 and style_norm not in ["manhwa", "manhua"]:
            return "panel_strip"
        if generation_format is None or generation_format == "" or generation_format.lower() in ["null", "none", "ai_decides", "default"]:
            # manhwa/manhua are single tall pages by nature. cinematic/realistic now
            # honour panel count (they were wrongly forced to single_page before).
            if style_norm in ["manhwa", "manhua"]:
                return "single_page"
            else:
                return "panel_strip"
        if panel_count == 1:
            return "single_page"
        return "panel_strip"

# Instantiate a global instance of ComicService
comic_service = ComicService()
