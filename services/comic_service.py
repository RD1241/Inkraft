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
        
        # Single worker to protect GPU from OOM
        self.job_executor = ThreadPoolExecutor(max_workers=1)

    def queue_comic_generation(self, text: str, style: str, panel_count: int = None, layout_type: str = None, user_id: str = None, characters: list = None) -> tuple[str, bool]:
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
                    panel_count_mode=panel_count_mode
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
            panel_count_mode=panel_count_mode
        )
        self.job_executor.submit(self.process_job_worker, job_id, text, style, panel_count, layout_type, user_id, characters)
        return job_id, False

    def process_job_worker(self, job_id: str, text: str, style: str = "anime", panel_count: int = None, layout_type: str = None, user_id: str = None, characters: list = None):
        """Background worker that handles the heavy AI generation pipeline."""
        start_time = time.time()
        
        # Instantiate active providers dynamically for this job
        llm_provider = get_llm_provider()
        image_provider = get_image_provider()
        storage_provider = get_storage_provider()
        
        try:
            self.job_manager.update_job(job_id, status="processing")

            # Step 0: Clear memory to prevent trait poisoning from previous run
            self.memory_manager.clear_memory()
            self.memory_manager.load_character_design_sheets(user_id, request_sheets=characters)

            # Step 1: LLM scene extraction
            self.job_manager.update_job(job_id, status="processing", progress="Extracting scenes with LLM...")
            scene_data = llm_provider.process_text(text, panel_count=panel_count, layout_type=layout_type)
            if not scene_data.get("scenes"):
                raise ValueError("Failed to extract scenes from text.")

            # Step 1.5: Storyboard planning BEFORE image generation starts [NEW - 2C]
            # StoryboardDirector plans the visual sequence and locks cinematic elements
            storyboard_plan = self.storyboard_director.plan(scene_data, panel_count=panel_count, layout_type=layout_type)
            total_panels = storyboard_plan.total_panels
            
            # Map the plan into scene_data to preserve all calculated metrics in metadata.json
            scene_data = storyboard_plan.to_dict()

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            job_output_dir = storage_provider.get_job_directory(timestamp)

            # Build a prompt_builder keyed to the detected style
            style_prompt_builder = PromptBuilder(style=style)

            output_images = []
            global_env = storyboard_plan.global_environment
            scene_seed = settings.SD_DEFAULT_SEED
            base_latents = image_provider.create_base_latents(scene_seed)

            # Step 2: Generate each panel in the storyboard
            for i, panel in enumerate(storyboard_plan.panels):
                panel_num = i + 1
                self.job_manager.update_job(
                    job_id, status="processing",
                    progress=f"Drawing panel {panel_num}/{total_panels}..."
                )

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

                # Update memory manager consistency profiles
                self.memory_manager.process_scene_characters(panel_scene)

                # Get dominant character for IP-Adapter consistency locks [NEW - 2E]
                dominant_char = self.memory_manager.consistency.get_dominant_character(panel_scene)
                
                use_reference = False
                character_reference_path = None
                if i > 0 and dominant_char:
                    ref_img = self.memory_manager.consistency.get_ip_adapter_reference(dominant_char, panel_index=i)
                    if ref_img and os.path.exists(ref_img):
                        character_reference_path = ref_img
                        use_reference = True

                # Build prompt using multi-layered PromptBuilder V2 [NEW - 2F]
                pos_prompt, neg_prompt = style_prompt_builder.build_prompt(
                    panel_scene, self.memory_manager, is_continuation=(i > 0), style=style
                )

                if use_reference:
                    pos_prompt, neg_prompt = style_prompt_builder.apply_reference_conditioning_prompt(pos_prompt, neg_prompt)

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
                        )
                        success = True
                        break
                    except Exception as e:
                        last_error = str(e)
                        print(f"[Warning] Panel {panel_num} attempt {attempt + 1} failed: {e}")
                        # Simplify prompt on retry
                        pos_prompt = pos_prompt.split(",")[0] + ", " + settings.MASTER_STYLE_TAG

                if not success:
                    raise RuntimeError(f"Panel {panel_num} failed after {settings.MAX_RETRIES} attempts: {last_error}")

                # Lock character anchor after Panel 1 generation is complete [NEW - 2E]
                if i == 0 and dominant_char:
                    character_reference_path = os.path.join(job_output_dir, f"{dominant_char.lower()}_ref.png")
                    try:
                        image_provider.extract_character_anchor(image_path, character_reference_path)
                        self.memory_manager.consistency.lock_character_anchor(dominant_char, character_reference_path)
                    except Exception as e:
                        print(f"[Warning] Character anchor extraction failed for {dominant_char}: {e}")
                        character_reference_path = None

                # Draw speech bubbles
                if panel.dialogue:
                    try:
                        self.comic_renderer.draw_speech_bubble(image_path, panel.dialogue, image_path)
                    except Exception as e:
                        print(f"[Warning] Speech bubble failed for panel {panel_num}: {e}")

                output_images.append(image_path)

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

        except Exception as e:
            gen_time = time.time() - start_time
            print(f"[Error] Job {job_id} failed: {e}")
            self.drift_monitor.log_job_metrics(job_id, text, [], gen_time, False, [])
            self.job_manager.update_job(job_id, status="failed", error=str(e))
            
            # Refund credit on generation failure
            if user_id:
                try:
                    from services.credits_service import credits_service
                    credits_service.refund_credit(user_id)
                    print(f"[CreditsService] Refunded 1 credit to user {user_id} due to generation failure.")
                except Exception as refund_err:
                    print(f"[Error] Failed to refund credit to user {user_id}: {refund_err}")

            # Always free VRAM on failure
            try:
                image_provider.unload_model()
            except Exception:
                pass

# Instantiate a global instance of ComicService
comic_service = ComicService()
