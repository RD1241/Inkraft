import os
from PIL import Image, ImageDraw, ImageFont
from config import settings

class ComicRenderer:
    def __init__(self):
        # We try to use a standard font, fallback to default if not found
        self.font_path = self._get_default_font()
        import threading
        self._rendered_lock = threading.Lock()
        self._rendered_dialogues = {}
        
    def _get_default_font(self):
        # Find a bold, readable TTF. Order: comic-friendly Windows fonts (local dev),
        # then Linux fonts (Railway/containers — installed via Dockerfile.railway's
        # fonts-dejavu-core), then macOS. CRITICAL: the slim Linux image ships NO fonts,
        # so without a Linux path here self.font_path was None and speech bubbles fell
        # back to PIL's tiny bitmap default → illegible dialogue on the live site. [QA 2026-06-30]
        candidates = [
            # Windows (local dev)
            "C:\\Windows\\Fonts\\comicbd.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf",
            "C:\\Windows\\Fonts\\comic.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
            # Linux (Railway / containers)
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            # macOS
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/Library/Fonts/Arial.ttf",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def _sized_default(self, size):
        """Sized fallback when no system TTF is found. Pillow>=10.1 scales the bundled
        default via load_default(size); on older Pillow it ignores size (tiny) — but the
        Dockerfile installs DejaVu so font_path is set on the live box and this is only a
        last-resort safety net so dialogue never renders microscopic."""
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()

    def _wrap_text(self, text: str, font, max_width: int, draw: ImageDraw) -> list:
        lines = []
        for manual_line in text.split('\n'):
            words = manual_line.split()
            current_line = []
            
            for word in words:
                current_line.append(word)
                bbox = draw.textbbox((0, 0), " ".join(current_line), font=font)
                if bbox[2] - bbox[0] > max_width:
                    if len(current_line) > 1:
                        current_line.pop()
                        lines.append(" ".join(current_line))
                        current_line = [word]
            if current_line:
                lines.append(" ".join(current_line))
        return lines

    def draw_speech_bubble(
        self,
        image_path: str,
        dialogues: list,
        output_path: str,
        panel_index: int = 0,
        style: str = "anime",
        layout_type: str = "standard",
        tension_level: int = 5,
        action_description: str = "",
        total_panels: int = 0
    ):
        """Draws professional manga-style speech bubbles, narration boxes, and sound effects."""
        import re
        import math
        index = panel_index
        if not index and image_path:
            match = re.search(r'scene_(\d+)', os.path.basename(image_path))
            if match:
                index = int(match.group(1))
            else:
                index = 1

        dialogues_list = dialogues if dialogues else []
        # Sort so narration boxes are processed first to prevent them being pushed down by top speech bubbles
        def is_narration_box(d):
            dlg_type = str(d.get("type", "speech")).lower()
            speaker = str(d.get("speaker", "")).lower()
            return dlg_type == "narration" or speaker == "narrator"
        dialogues_list = sorted(dialogues_list, key=lambda d: 0 if is_narration_box(d) else 1)

        print(f"[Renderer] Panel {index}: {len(dialogues_list)} dialogue bubbles to render")

        if (index == 0 or index == 1) and total_panels >= 3 and dialogues_list:
            print(f"[Renderer] WARNING: Dialogue on Panel 1 of {total_panels} — consider moving")

        try:
            img = Image.open(image_path).convert("RGBA")
            overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(overlay)
            
            # Recalculate speech bubble parameters relative to actual panel dimensions.
            # Bumped from 0.024 -> 0.040 (min 22) so bubble text stays legible once the
            # finished page is displayed scaled-down in the UI.
            font_size = max(22, int(img.width * 0.040))
            
            # Bubble Style configuration
            style_name = style.lower() if style else "anime"
            if style_name == "manga":
                bg_color = (255, 255, 255, 255)
                border_color = (0, 0, 0, 255)
                border_width = 3
                text_fill_color = (0, 0, 0, 255)
                shadow_fill_color = None
                tail_style = "manga"
                text_case = "uppercase"
            elif style_name == "manhwa":
                bg_color = (255, 255, 255, 255)
                border_color = (34, 34, 34, 255) # #222222
                border_width = 2
                text_fill_color = (0, 0, 0, 255)
                shadow_fill_color = (0, 0, 0, 60) # soft shadow
                tail_style = "manhwa"
                text_case = "normal"
            elif style_name == "cinematic":
                bg_color = (255, 255, 255, 255)
                border_color = (0, 0, 0, 255)
                border_width = 2
                text_fill_color = (0, 0, 0, 255)
                shadow_fill_color = None
                tail_style = "cinematic"
                text_case = "normal"
            else:
                bg_color = (255, 255, 255, 255)
                border_color = (0, 0, 0, 255)
                border_width = 2
                text_fill_color = (0, 0, 0, 255)
                shadow_fill_color = (0, 0, 0, 80)
                tail_style = "manga"
                text_case = "normal"

            # Setup fonts
            speech_font = None
            narration_font = None
            if self.font_path:
                try:
                    speech_font = ImageFont.truetype(self.font_path, font_size)
                    # For narration, use non-bold version if available
                    regular_font_path = (self.font_path
                        .replace("arialbd.ttf", "arial.ttf")
                        .replace("comicbd.ttf", "comic.ttf")
                        .replace("DejaVuSans-Bold.ttf", "DejaVuSans.ttf")
                        .replace("LiberationSans-Bold.ttf", "LiberationSans-Regular.ttf"))
                    if os.path.exists(regular_font_path):
                        narration_font = ImageFont.truetype(regular_font_path, font_size)
                    else:
                        narration_font = speech_font
                except IOError:
                    speech_font = self._sized_default(font_size)
                    narration_font = speech_font
            else:
                speech_font = self._sized_default(font_size)
                narration_font = speech_font

            # Positioning logic
            positions = ['top-left', 'bottom-right', 'top-right', 'bottom-left']
            # Alternate start corner based on panel_index
            start_pos_idx = (index - 1) % 4
            
            y_offset = 20
            bottom_y_offset = 30
            used_corners = []
            rendered_rects = []

            active_dialogues_count = 0
            for i, dialogue in enumerate(dialogues_list):
                speaker = str(dialogue.get("speaker", "Unknown")).strip()
                dlg_type = str(dialogue.get("type", "speech")).lower()
                is_narration = (dlg_type == "narration" or speaker.lower() == "narrator")
                
                # Format and clean text
                raw_text = dialogue.get('text', '').strip()
                
                # Strip character name prefixes
                if speaker:
                    spk_clean = speaker.lower()
                    for sep in ["/", ":", "-", "—"]:
                        for pattern in [f"{spk_clean}{sep}", f"{spk_clean} {sep}"]:
                            if raw_text.lower().startswith(pattern):
                                raw_text = raw_text[len(pattern):].strip()
                        if sep in raw_text:
                            parts = raw_text.split(sep, 1)
                            if parts[0].strip().lower() == spk_clean:
                                raw_text = parts[1].strip()
                                
                while raw_text.startswith(':') or raw_text.startswith('/') or raw_text.startswith('-') or raw_text.startswith('"') or raw_text.startswith("'"):
                    raw_text = raw_text[1:].strip()
                while raw_text.endswith('"') or raw_text.endswith("'"):
                    raw_text = raw_text[:-1].strip()
                
                raw_text = " ".join(raw_text.split())
                if not raw_text:
                    continue

                # Check for duplicate dialogue string across panels in this comic (Fix 1)
                job_dir = os.path.dirname(image_path) if image_path else "default_job"
                with self._rendered_lock:
                    if job_dir not in self._rendered_dialogues:
                        self._rendered_dialogues[job_dir] = set()
                    dialogue_key = raw_text.lower()
                    if dialogue_key in self._rendered_dialogues[job_dir]:
                        print(f"[Renderer] Skipping duplicate dialogue bubble in panel {index}: '{raw_text}'")
                        continue
                    self._rendered_dialogues[job_dir].add(dialogue_key)

                # Now determine position since we are definitely rendering this bubble
                if is_narration:
                    pos = "top-center"
                else:
                    pos = positions[(start_pos_idx + active_dialogues_count) % len(positions)]
                    used_corners.append(pos)
                    active_dialogues_count += 1

                text = raw_text

                # Text Case transformation
                if not is_narration and text_case == "uppercase" and dlg_type != "thought":
                    text = text.upper()

                # Padding based on text length, scaled to font size to avoid clipping
                text_len = len(text)
                if text_len < 20:
                    padding_x = int(font_size * 0.8)
                    padding_y = int(font_size * 0.5)
                elif text_len <= 60:
                    padding_x = int(font_size * 1.1)
                    padding_y = int(font_size * 0.7)
                else:
                    padding_x = int(font_size * 1.4)
                    padding_y = int(font_size * 0.9)

                # Maximum width limit (75% for narration, 62% for speech bubbles —
                # wider bubbles fit larger, more readable text with fewer cramped wraps)
                if is_narration:
                    max_width = int(img.width * 0.75)
                else:
                    max_width = int(img.width * 0.62)

                # Setup fonts and scale down font size if text is very long relative to panel size
                active_font = narration_font if is_narration else speech_font
                if not is_narration and self.font_path:
                    # Only gently shrink very long dialogue; keep it readable (min 18).
                    if text_len > 200:
                        active_font = ImageFont.truetype(self.font_path, max(18, int(font_size * 0.8)))
                    elif text_len > 100:
                        active_font = ImageFont.truetype(self.font_path, max(18, int(font_size * 0.9)))

                lines = self._wrap_text(text, active_font, max_width, draw)
                if not lines:
                    continue
                    
                line_height = draw.textbbox((0, 0), lines[0], font=active_font)[3] - draw.textbbox((0, 0), lines[0], font=active_font)[1]
                text_width = max([draw.textbbox((0, 0), line, font=active_font)[2] - draw.textbbox((0, 0), line, font=active_font)[0] for line in lines])
                
                bubble_width = text_width + (padding_x * 2)
                bubble_height = (line_height * len(lines)) + (padding_y * 2) + (len(lines) * 4)

                # Calculate Coordinates
                if is_narration:
                    # Narration boxes always at top, centered horizontally
                    y = y_offset
                    y_offset += bubble_height + 15
                    x = (img.width - bubble_width) // 2
                else:
                    if pos.startswith('top'):
                        y = y_offset
                        y_offset += bubble_height + 25
                    else:
                        y = img.height - bubble_height - bottom_y_offset
                        bottom_y_offset += bubble_height + 25

                    if pos.endswith('left'):
                        x = 20
                    else:
                        x = img.width - bubble_width - 20
                
                # Bounds clamping
                x = max(10, min(x, img.width - bubble_width - 10))
                y = max(10, min(y, img.height - bubble_height - 10))

                # Check and resolve overlaps with previously drawn bubbles
                overlap = True
                attempts = 0
                while overlap and attempts < 10:
                    overlap = False
                    for rx1, ry1, rx2, ry2 in rendered_rects:
                        # Check if current rect overlaps with this rendered rect
                        if not (x + bubble_width < rx1 or x > rx2 or y + bubble_height < ry1 or y > ry2):
                            overlap = True
                            # Adjust y depending on position
                            if is_narration:
                                y = ry2 + 10
                            elif pos.startswith('top'):
                                y = ry2 + 10
                            else:
                                y = ry1 - bubble_height - 10
                            
                            # Re-clamp coordinates
                            x = max(10, min(x, img.width - bubble_width - 10))
                            y = max(10, min(y, img.height - bubble_height - 10))
                            break
                    attempts += 1

                # Add to rendered rects
                rendered_rects.append((x, y, x + bubble_width, y + bubble_height))

                if is_narration:
                    # Narration Box
                    box_fill = (20, 20, 20, 230)
                    text_fill = (255, 255, 255, 255)
                    outline_fill = (255, 255, 255, 200)
                    draw.rectangle([x, y, x + bubble_width, y + bubble_height], fill=box_fill, outline=outline_fill, width=2)
                else:
                    # Speech Bubble outline & shadow
                    if shadow_fill_color:
                        draw.rounded_rectangle([x + 4, y + 4, x + bubble_width + 4, y + bubble_height + 4], radius=15, fill=shadow_fill_color)
                    
                    draw.rounded_rectangle([x, y, x + bubble_width, y + bubble_height], radius=15, fill=bg_color, outline=border_color, width=border_width)
                    
                    # Tail drawing based on style
                    tail_base_x = x + (bubble_width // 2)
                    if tail_style == "cinematic":
                        # Rectangular tail
                        if pos.startswith('top'):
                            tail_rect = [tail_base_x - 6, y + bubble_height - 3, tail_base_x + 6, y + bubble_height + 15]
                        else:
                            tail_rect = [tail_base_x - 6, y - 15, tail_base_x + 6, y + 3]
                        draw.rectangle(tail_rect, fill=bg_color, outline=border_color, width=border_width)
                    elif tail_style == "manhwa":
                        # Smooth curved tail
                        if pos.startswith('top'):
                            tail_poly = [
                                (tail_base_x - 10, y + bubble_height - 3),
                                (tail_base_x + 10, y + bubble_height - 3),
                                (tail_base_x + 5, y + bubble_height + 12),
                                (tail_base_x - 12, y + bubble_height + 18),
                                (tail_base_x - 5, y + bubble_height + 8)
                            ]
                        else:
                            tail_poly = [
                                (tail_base_x - 10, y + 3),
                                (tail_base_x + 10, y + 3),
                                (tail_base_x + 12, y - 8),
                                (tail_base_x + 5, y - 18),
                                (tail_base_x - 5, y - 10)
                            ]
                        draw.polygon(tail_poly, fill=bg_color, outline=border_color)
                        if pos.startswith('top'):
                            draw.line([(tail_base_x - 8, y + bubble_height - 3), (tail_base_x + 8, y + bubble_height - 3)], fill=bg_color, width=4)
                        else:
                            draw.line([(tail_base_x - 8, y + 3), (tail_base_x + 8, y + 3)], fill=bg_color, width=4)
                    else:
                        # Manga style: sharp angular tail
                        if pos.startswith('top'):
                            tail_len = max(5, min(25, img.height - (y + bubble_height) - 5))
                            tail_tip_y = y + bubble_height + tail_len
                            tail_polygon = [(tail_base_x - 10, y + bubble_height - 3), (tail_base_x + 10, y + bubble_height - 3), (tail_base_x - 15, tail_tip_y)]
                            draw.polygon(tail_polygon, fill=bg_color, outline=border_color)
                            draw.line([(tail_base_x - 9, y + bubble_height - 3), (tail_base_x + 9, y + bubble_height - 3)], fill=bg_color, width=4)
                        else:
                            tail_len = max(5, min(25, y - 5))
                            tail_tip_y = y - tail_len
                            tail_polygon = [(tail_base_x - 10, y + 3), (tail_base_x + 10, y + 3), (tail_base_x + 15, tail_tip_y)]
                            draw.polygon(tail_polygon, fill=bg_color, outline=border_color)
                            draw.line([(tail_base_x - 9, y + 3), (tail_base_x + 9, y + 3)], fill=bg_color, width=4)

                # Draw Text
                text_y = y + padding_y
                text_color = (255, 255, 255, 255) if is_narration else text_fill_color
                for line in lines:
                    line_w = draw.textbbox((0, 0), line, font=active_font)[2] - draw.textbbox((0, 0), line, font=active_font)[0]
                    line_x = x + (bubble_width - line_w) // 2
                    draw.text((line_x, text_y), line, font=active_font, fill=text_color)
                    text_y += line_height + 2

            # 5. Emotion sound effects for action panels (Manga Sound Effects)
            action_desc_lower = action_description.lower() if action_description else ""
            sound_effect = None
            
            # Action keywords mapping
            is_sword = any(w in action_desc_lower for w in ["sword", "blade", "slash", "steel", "clash", "clang"])
            is_strike = any(w in action_desc_lower for w in ["strike", "punch", "kick", "hit", "slam", "smash", "thud", "crack", "clashed"])
            is_explosion = any(w in action_desc_lower for w in ["explosion", "burst", "boom", "blast", "crash"])
            is_movement = any(w in action_desc_lower for w in ["footstep", "run", "stomp", "dash", "chase"])
            
            has_trigger_keyword = is_sword or is_strike or is_explosion or is_movement

            # Quiet / emotional beats must NOT get a combat SFX, even inside an "action"
            # comic and even if a weapon noun is present ("lowered his sword", "knelt
            # before the crying girl"). Suppress on tender keywords. [QA 2026-06-28]
            quiet_kw = ("kneel", "knelt", "comfort", "smile", "cry", "cries", "crying",
                        "cried", "tear", "weep", "wept", "sob", "whisper", "hug", "embrace",
                        "gentle", "calm", "lower", "sheath", "rest", "sleep", "soothe",
                        "reassur", "peace", "tender", "quietly", "silent", "knee", "hold",
                        "mourn", "grief", "pray", "kiss", "caress")
            is_quiet = any(w in action_desc_lower for w in quiet_kw)

            # Fire ONLY on a genuine combat/impact keyword in THIS panel's action, and
            # never on a quiet beat. (The old "any action-layout panel with tension>=7"
            # rule wrongly slapped SMASH! onto a knight comforting a child.)
            should_trigger = has_trigger_keyword and not is_quiet and (style_name not in ["manhwa", "manhua"])
            
            if should_trigger:
                import random
                # Choose the style variant and SFX text
                if is_sword:
                    # Sword/blade actions
                    sound_effect = "SLASH!" if "slash" in action_desc_lower else ("CLANG!" if "clang" in action_desc_lower else "CLASH!")
                    angle = random.uniform(-10, 10)
                    sfx_pos_type = "center-right"
                elif is_strike:
                    # Punch/strike actions
                    sound_effect = "CRACK!" if "crack" in action_desc_lower else ("THUD!" if "thud" in action_desc_lower else "SMASH!")
                    angle = random.uniform(-15, 5)
                    sfx_pos_type = "center"
                elif is_explosion:
                    # Explosion/burst actions
                    sound_effect = "BOOM!" if "boom" in action_desc_lower else ("BLAST!" if "blast" in action_desc_lower else "KA-BOOM!")
                    angle = random.uniform(-5, 15)
                    sfx_pos_type = "upper-center"
                elif is_movement:
                    # Footstep/movement actions
                    sound_effect = "STOMP!" if "stomp" in action_desc_lower else "DASH!"
                    angle = random.uniform(0, 10)
                    sfx_pos_type = "lower-center"
                else:
                    # Fallback / other
                    sound_effect = "CLASH!"
                    angle = random.uniform(-15, 15)
                    sfx_pos_type = "center-right"

                # Log sound effect state (Fix 3)
                print(f"[Renderer] Panel {index}: tension={tension_level}, layout={layout_type}, SFX={sound_effect}")
                print(f"[Renderer] Panel {index}: SFX={sound_effect}")

                # Scale SFX to the panel + tension so it reads with real manga impact
                # (the old fixed 48px was tiny on a 1024px panel) — but keep the burst
                # within the frame: shorter SFX get a touch bigger. [QA 2026-06-28]
                _base = max(48, int(img.width * 0.075))
                if tension_level >= 9:
                    _base = int(_base * 1.15)
                if len(sound_effect) <= 6:   # CLASH!, BOOM!, SLASH! — room to grow
                    _base = int(_base * 1.15)
                sfx_font_size = _base
                sfx_font = None
                sfx_font_path_used = "PIL default"
                font_paths = [
                    "C:/Windows/Fonts/arialbd.ttf",     # Windows Arial Bold
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",  # Linux
                    "/System/Library/Fonts/Helvetica.ttc",  # Mac
                ]
                for path in font_paths:
                    if os.path.exists(path):
                        try:
                            sfx_font = ImageFont.truetype(path, sfx_font_size)
                            sfx_font_path_used = path
                            break
                        except Exception:
                            pass
                if sfx_font is None:
                    # Try using self.font_path if available
                    if self.font_path and os.path.exists(self.font_path):
                        try:
                            sfx_font = ImageFont.truetype(self.font_path, sfx_font_size)
                            sfx_font_path_used = self.font_path
                        except Exception:
                            pass
                if sfx_font is None:
                    try:
                        sfx_font = ImageFont.load_default(size=sfx_font_size)
                    except Exception:
                        sfx_font = ImageFont.load_default()
                    sfx_font_path_used = "PIL default"
                print(f"[Renderer] SFX font: {sfx_font_path_used}")

                sfx_bbox = draw.textbbox((0, 0), sound_effect, font=sfx_font)
                sfx_w = sfx_bbox[2] - sfx_bbox[0]
                sfx_h = sfx_bbox[3] - sfx_bbox[1]

                # Position selection based on whether speech bubbles exist (preventing collision)
                if used_corners:
                    first_bubble = used_corners[0]
                    if first_bubble == "top-left":
                        sfx_x = int(img.width * 0.75) - sfx_w // 2
                        sfx_y = int(img.height * 0.75) - sfx_h // 2
                        sfx_pos_type = "bottom-right"
                    elif first_bubble == "top-right":
                        sfx_x = int(img.width * 0.25) - sfx_w // 2
                        sfx_y = int(img.height * 0.75) - sfx_h // 2
                        sfx_pos_type = "bottom-left"
                    elif first_bubble == "bottom-left":
                        sfx_x = int(img.width * 0.75) - sfx_w // 2
                        sfx_y = int(img.height * 0.25) - sfx_h // 2
                        sfx_pos_type = "top-right"
                    elif first_bubble == "bottom-right":
                        sfx_x = int(img.width * 0.25) - sfx_w // 2
                        sfx_y = int(img.height * 0.25) - sfx_h // 2
                        sfx_pos_type = "top-left"
                    else:
                        sfx_x = int(img.width * 0.5) - sfx_w // 2
                        sfx_y = int(img.height * 0.5) - sfx_h // 2
                        sfx_pos_type = "center"
                else:
                    # If no speech bubble exists, position near the center-right of the panel
                    sfx_x = int(img.width * 0.70) - sfx_w // 2
                    sfx_y = int(img.height * 0.50) - sfx_h // 2
                    sfx_pos_type = "center-right"

                sfx_x = max(15, min(sfx_x, img.width - sfx_w - 15))
                sfx_y = max(15, min(sfx_y, img.height - sfx_h - 15))

                # Manga impact effect: a jagged white starburst (black outline) behind
                # bold black text with a white halo. Reads on any background and gives a
                # real comic "impact" feel instead of plain floating text. [QA 2026-06-28]
                import math
                pad = int(max(sfx_w, sfx_h) * 0.42) + 28
                temp_w = sfx_w + pad * 2
                temp_h = sfx_h + pad * 2
                text_img = Image.new("RGBA", (temp_w, temp_h), (0, 0, 0, 0))
                t_draw = ImageDraw.Draw(text_img)

                cx, cy = temp_w / 2, temp_h / 2
                outer_r = max(sfx_w, sfx_h) / 2 + pad * 0.6
                inner_r = outer_r * 0.66
                spikes = 14
                burst = []
                for i in range(spikes * 2):
                    r = outer_r if i % 2 == 0 else inner_r
                    # slight per-spike jitter so the burst looks hand-inked, not geometric
                    rr = r * random.uniform(0.9, 1.08)
                    a = math.pi * i / spikes
                    burst.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
                # black outline burst, then white fill slightly inset
                t_draw.polygon(burst, fill=(0, 0, 0, 255))
                burst_in = [(cx + (px - cx) * 0.93, cy + (py - cy) * 0.93) for px, py in burst]
                t_draw.polygon(burst_in, fill=(255, 255, 255, 255))

                # Bold black text with a thick white halo, centred on the burst
                tx = cx - sfx_w / 2 - sfx_bbox[0]
                ty = cy - sfx_h / 2 - sfx_bbox[1]
                halo = 5
                for ox in range(-halo, halo + 1, 2):
                    for oy in range(-halo, halo + 1, 2):
                        if ox or oy:
                            t_draw.text((tx + ox, ty + oy), sound_effect, font=sfx_font, fill=(255, 255, 255, 255))
                t_draw.text((tx, ty), sound_effect, font=sfx_font, fill=(0, 0, 0, 255))

                rotated_img = text_img.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)

                # Centre the (expanded) burst on the intended SFX point so the larger
                # canvas + rotation don't drift it off-target.
                paste_x = int(sfx_x + sfx_w / 2 - rotated_img.width / 2)
                paste_y = int(sfx_y + sfx_h / 2 - rotated_img.height / 2)
                paste_x = max(0, min(paste_x, img.width - rotated_img.width))
                paste_y = max(0, min(paste_y, img.height - rotated_img.height))
                overlay.paste(rotated_img, (paste_x, paste_y), rotated_img)
                print(f"[Renderer] Sound effect '{sound_effect}' rendered at corner '{sfx_pos_type}' with angle {angle:.1f}°")

            # Combine overlay with image
            final_img = Image.alpha_composite(img, overlay).convert("RGB")
            final_img.save(output_path)
            return output_path
            
        except Exception as e:
            print(f"Error drawing speech bubble/SFX: {e}")
            return image_path

    def _add_watermark_to_pillow_image(self, img: Image.Image) -> Image.Image:
        """Draws a subtle white watermark (30% opacity) in the bottom-right corner."""
        was_rgb = img.mode == "RGB"
        img_rgba = img.convert("RGBA")
        
        txt_overlay = Image.new("RGBA", img_rgba.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_overlay)
        
        font = None
        if self.font_path:
            try:
                font = ImageFont.truetype(self.font_path, 24)
            except IOError:
                font = self._sized_default(24)
        else:
            font = self._sized_default(24)
            
        text = getattr(settings, "WATERMARK_TEXT", "Inkraft.ai")
        
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = img_rgba.width - text_width - 20
        y = img_rgba.height - text_height - 20
        
        x = max(10, x)
        y = max(10, y)
        
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 76))
        
        watermarked = Image.alpha_composite(img_rgba, txt_overlay)
        
        if was_rgb:
            return watermarked.convert("RGB")
        return watermarked

    def export_pdf(self, panel_images: list, layout, output_path: str, is_free: bool = False):
        """
        Exports the comic panels as a single elegant A4 PDF page, maintaining scaling and gutters.
        """
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        
        # A4 Page dimensions (points)
        pdf_w, pdf_h = A4
        
        # Dimensions of standard canvas
        canvas_w = 1024
        canvas_h = 1450
        
        # Scale to fit A4 page perfectly, preserving aspect ratio
        scale = min(pdf_w / canvas_w, pdf_h / canvas_h)
        
        # Center on the PDF page
        offset_x = (pdf_w - canvas_w * scale) / 2
        offset_y = (pdf_h - canvas_h * scale) / 2
        
        c = canvas.Canvas(output_path, pagesize=A4)
        
        # Draw a beautiful dark background (matching the comic page black gutters)
        c.setFillColorRGB(0, 0, 0)
        c.rect(0, 0, pdf_w, pdf_h, fill=True, stroke=False)
        
        # Handle panel coords
        panels = []
        if hasattr(layout, "panels"):
            panels = layout.panels
        elif isinstance(layout, dict) and "panels" in layout:
            panels = layout["panels"]
        else:
            panels = layout
            
        for i, panel in enumerate(panels):
            if i >= len(panel_images):
                break
                
            panel_image_path = panel_images[i]
            
            # Extract panel coordinates
            px, py, pw, ph = 0, 0, 0, 0
            if hasattr(panel, "x"):
                px, py, pw, ph = panel.x, panel.y, panel.width, panel.height
            elif isinstance(panel, dict):
                px = panel.get("x", 0)
                py = panel.get("y", 0)
                pw = panel.get("width", 0)
                ph = panel.get("height", 0)
            else:
                continue
                
            # Scale coordinates and dimensions
            # ReportLab y=0 starts at bottom-left, Pillow y=0 starts at top-left
            scaled_w = pw * scale
            scaled_h = ph * scale
            scaled_x = offset_x + px * scale
            scaled_y = offset_y + (canvas_h - (py + ph)) * scale
            
            # Draw elegant white border around the panel just like custom Pillow layout
            border = 3 * scale
            c.setFillColorRGB(1, 1, 1)
            c.rect(scaled_x - border, scaled_y - border, scaled_w + 2 * border, scaled_h + 2 * border, fill=True, stroke=False)
            
            # Draw the panel image on top
            c.drawImage(panel_image_path, scaled_x, scaled_y, width=scaled_w, height=scaled_h)
            
        # Draw subtle white watermark for free users in bottom-right corner
        if is_free:
            try:
                c.setFont("Helvetica-Bold", 14)
                c.setFillColorRGB(1, 1, 1)
                if hasattr(c, "setFillAlpha"):
                    c.setFillAlpha(0.3)
                watermark = getattr(settings, "WATERMARK_TEXT", "Inkraft.ai")
                c.drawRightString(pdf_w - 20, 20, watermark)
                if hasattr(c, "setFillAlpha"):
                    c.setFillAlpha(1.0)
            except Exception as we:
                print(f"[Warning] PDF Watermarking failed: {we}")
                
        c.showPage()
        c.save()
        return output_path

    def create_comic_page(self, image_paths: list, output_path: str, is_free: bool = False):
        """Stitches multiple panels into a grid-based comic page layout, using PanelCompositor if possible."""
        if not image_paths:
            return None
            
        try:
            import json
            from core.panel_compositor import PanelCompositor
            
            # Find metadata.json in the same directory as panel images
            metadata_path = None
            if image_paths and os.path.exists(image_paths[0]):
                dir_name = os.path.dirname(image_paths[0])
                meta_candidate = os.path.join(dir_name, "metadata.json")
                if os.path.exists(meta_candidate):
                    metadata_path = meta_candidate
            
            if not metadata_path:
                raise ValueError("metadata.json not found in job directory.")
                
            with open(metadata_path, "r", encoding="utf-8") as f:
                scene_data = json.load(f)
                
            scenes = scene_data.get("scenes") or scene_data.get("panels")
            if not scenes:
                raise ValueError("No scenes or panels found in metadata.")
                
            if len(scenes) != len(image_paths):
                raise ValueError(f"Metadata has {len(scenes)} scenes but got {len(image_paths)} images.")
                
            # Create Custom Layout Page
            compositor = PanelCompositor()
            layout_type = scene_data.get("layout_type") or "standard"
            page_layout = compositor.calculate_layout(scenes, layout_type=layout_type)
            
            result = self.create_custom_layout_page(image_paths, page_layout, output_path, is_free=is_free)
            
            # Log success
            msg = f"[PanelCompositor] Custom layout applied: {len(image_paths)} panels, layout_type: {layout_type}"
            print(msg)
            import logging
            logging.getLogger("ComicRenderer").info(msg)
            
            return result
            
        except Exception as e:
            # On fallback, log a warning
            warn_msg = f"[PanelCompositor] FALLBACK: using grid layout — reason: {e}"
            print(warn_msg)
            import logging
            logging.getLogger("ComicRenderer").warning(warn_msg)
            
            # Use original grid layout
            return self._create_grid_comic_page(image_paths, output_path, is_free=is_free)

    def _create_grid_comic_page(self, image_paths: list, output_path: str, is_free: bool = False):
        """Stitches multiple panels into a grid-based comic page layout (Fallback)."""
        if not image_paths:
            return None
            
        try:
            images = [Image.open(p) for p in image_paths]
            
            num_images = len(images)
            cols = 2 if num_images > 2 else 1
            rows = (num_images + cols - 1) // cols
            
            panel_width = images[0].width
            panel_height = images[0].height
            
            padding = 15 # Manga usually has tight gutters
            
            page_width = (panel_width * cols) + (padding * (cols + 1))
            page_height = (panel_height * rows) + (padding * (rows + 1))
            
            # Black background is standard for modern webtoons/dark fantasy manga
            page = Image.new("RGB", (page_width, page_height), "black")
            
            for i, img in enumerate(images):
                row = i // cols
                col = i % cols
                
                x = padding + (col * (panel_width + padding))
                y = padding + (row * (panel_height + padding))
                
                img = img.resize((panel_width, panel_height))
                
                # White border for panels on a black background
                bordered_img = Image.new("RGB", (panel_width + 6, panel_height + 6), "white")
                bordered_img.paste(img, (3, 3))
                
                page.paste(bordered_img, (x-3, y-3))
                
            if is_free:
                page = self._add_watermark_to_pillow_image(page)
                
            page.save(output_path)
            return output_path
            
        except Exception as e:
            print(f"Error creating comic page: {e}")
            return None

    def create_custom_layout_page(self, image_paths: list, layout, output_path: str, is_free: bool = False):
        """
        Renders a custom comic page layout based on PanelCompositor PageLayout.
        Resizes panel images to exact panel dimensions and places them at calculated x, y.
        """
        try:
            page_width = 1024
            page_height = 1450
            
            # Black background for dynamic panel layout
            page = Image.new("RGB", (page_width, page_height), "black")
            
            for i, panel in enumerate(layout.panels):
                if i >= len(image_paths):
                    break
                    
                img = Image.open(image_paths[i])

                # Fit the panel art into its slot WITHOUT distortion. The slots have
                # varied aspect ratios (some very wide/short) that the generated art
                # can't match, and a plain resize STRETCHED the art — squishing faces
                # and making the page look "compressed/forced". Use object-fit:cover —
                # scale preserving aspect to fill the slot, then centre-crop the
                # overflow — so proportions are always preserved. [QA 2026-06-30]
                target_w, target_h = panel.width, panel.height
                if img.size == (target_w, target_h):
                    resized_img = img
                else:
                    src_w, src_h = img.size
                    scale = max(target_w / src_w, target_h / src_h)
                    new_w = max(target_w, int(round(src_w * scale)))
                    new_h = max(target_h, int(round(src_h * scale)))
                    scaled = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    left = (new_w - target_w) // 2
                    top = (new_h - target_h) // 2
                    resized_img = scaled.crop((left, top, left + target_w, top + target_h))
                
                # White border (3px on each side = +6px total)
                bordered_img = Image.new("RGB", (panel.width + 6, panel.height + 6), "white")
                bordered_img.paste(resized_img, (3, 3))
                
                # Paste at coordinates (offset border)
                page.paste(bordered_img, (panel.x - 3, panel.y - 3))
                
            if is_free:
                page = self._add_watermark_to_pillow_image(page)
                
            page.save(output_path)
            return output_path
            
        except Exception as e:
            raise RuntimeError(f"Error in create_custom_layout_page: {e}")

    def create_single_page(
        self,
        image,
        dialogue: str,
        narration: str,
        style: str,
        watermark: bool
    ) -> Image.Image:
        """
        Renders a single-page webtoon-style comic page.
        Resizes and crops image to 1024x1450, overlays narration at top, dialogue above the bottom 150px,
        and optionally adds the Inkraft watermark.
        """
        target_w, target_h = 1024, 1450
        w, h = image.size
        
        # 1. Resize and crop from center if aspect ratio differs
        if w != target_w or h != target_h:
            target_ratio = target_w / target_h
            current_ratio = w / h
            if current_ratio > target_ratio:
                new_w = int(h * target_ratio)
                left = (w - new_w) // 2
                image = image.crop((left, 0, left + new_w, h))
            else:
                new_h = int(w / target_ratio)
                top = (h - new_h) // 2
                image = image.crop((0, top, w, top + new_h))
            image = image.resize((target_w, target_h), Image.Resampling.LANCZOS)

        img_rgba = image.convert("RGBA")
        overlay = Image.new("RGBA", img_rgba.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)

        # 2. Add dark semi-transparent narration box at TOP of image
        if narration and narration.strip():
            box_fill = (20, 20, 20, 180)
            draw.rectangle([0, 0, target_w, 80], fill=box_fill)
            
            font_size = 18
            try:
                italic_font_path = self.font_path.replace("arialbd.ttf", "ariali.ttf").replace("arial.ttf", "ariali.ttf")
                if not os.path.exists(italic_font_path):
                    italic_font_path = "C:\\Windows\\Fonts\\ariali.ttf"
                if os.path.exists(italic_font_path):
                    n_font = ImageFont.truetype(italic_font_path, font_size)
                elif self.font_path:
                    n_font = ImageFont.truetype(self.font_path, font_size)
                else:
                    n_font = self._sized_default(font_size)
            except Exception:
                n_font = self._sized_default(font_size)

            lines = self._wrap_text(narration, n_font, target_w - 60, draw)
            line_height = draw.textbbox((0, 0), lines[0], font=n_font)[3] - draw.textbbox((0, 0), lines[0], font=n_font)[1] if lines else 20
            
            total_h = len(lines) * (line_height + 4)
            text_y = (80 - total_h) // 2
            
            for line in lines:
                line_w = draw.textbbox((0, 0), line, font=n_font)[2] - draw.textbbox((0, 0), line, font=n_font)[0]
                line_x = (target_w - line_w) // 2
                draw.text((line_x, text_y), line, font=n_font, fill=(255, 255, 255, 255))
                text_y += line_height + 4

        final_img = Image.alpha_composite(img_rgba, overlay)

        # 3. Add speech bubble above the lower 150px
        if dialogue:
            rgb_img = final_img.convert("RGB")
            overlay_dlg = Image.new("RGBA", rgb_img.size, (255, 255, 255, 0))
            draw_dlg = ImageDraw.Draw(overlay_dlg)

            # Style configuration (matching draw_speech_bubble)
            style_name = style.lower() if style else "anime"
            if style_name == "manga":
                bg_color = (255, 255, 255, 255)
                border_color = (0, 0, 0, 255)
                border_width = 3
                text_fill_color = (0, 0, 0, 255)
                shadow_fill_color = None
                tail_style = "manga"
                text_case = "uppercase"
            elif style_name == "manhwa":
                bg_color = (255, 255, 255, 255)
                border_color = (34, 34, 34, 255)
                border_width = 2
                text_fill_color = (0, 0, 0, 255)
                shadow_fill_color = (0, 0, 0, 60)
                tail_style = "manhwa"
                text_case = "normal"
            elif style_name == "cinematic":
                bg_color = (255, 255, 255, 255)
                border_color = (0, 0, 0, 255)
                border_width = 2
                text_fill_color = (0, 0, 0, 255)
                shadow_fill_color = None
                tail_style = "cinematic"
                text_case = "normal"
            else:
                bg_color = (255, 255, 255, 255)
                border_color = (0, 0, 0, 255)
                border_width = 2
                text_fill_color = (0, 0, 0, 255)
                shadow_fill_color = (0, 0, 0, 80)
                tail_style = "manga"
                text_case = "normal"

            font_size = 18
            try:
                speech_font = ImageFont.truetype(self.font_path, font_size) if self.font_path else self._sized_default(font_size)
            except Exception:
                speech_font = self._sized_default(font_size)

            text = dialogue
            if text_case == "uppercase":
                text = text.upper()

            lines = self._wrap_text(text, speech_font, int(target_w * 0.5), draw_dlg)
            if lines:
                line_height = draw_dlg.textbbox((0, 0), lines[0], font=speech_font)[3] - draw_dlg.textbbox((0, 0), lines[0], font=speech_font)[1]
                text_width = max([draw_dlg.textbbox((0, 0), line, font=speech_font)[2] - draw_dlg.textbbox((0, 0), line, font=speech_font)[0] for line in lines])
                
                padding_x = 20
                padding_y = 14
                bubble_width = text_width + (padding_x * 2)
                bubble_height = (line_height * len(lines)) + (padding_y * 2) + (len(lines) * 4)

                x = (target_w - bubble_width) // 2
                y = target_h - 150 - bubble_height

                if shadow_fill_color:
                    draw_dlg.rounded_rectangle([x + 4, y + 4, x + bubble_width + 4, y + bubble_height + 4], radius=15, fill=shadow_fill_color)
                draw_dlg.rounded_rectangle([x, y, x + bubble_width, y + bubble_height], radius=15, fill=bg_color, outline=border_color, width=border_width)

                tail_base_x = target_w // 2
                if tail_style == "cinematic":
                    tail_rect = [tail_base_x - 6, y + bubble_height - 3, tail_base_x + 6, y + bubble_height + 15]
                    draw_dlg.rectangle(tail_rect, fill=bg_color, outline=border_color, width=border_width)
                elif tail_style == "manhwa":
                    tail_poly = [
                        (tail_base_x - 10, y + bubble_height - 3),
                        (tail_base_x + 10, y + bubble_height - 3),
                        (tail_base_x + 5, y + bubble_height + 12),
                        (tail_base_x - 12, y + bubble_height + 18),
                        (tail_base_x - 5, y + bubble_height + 8)
                    ]
                    draw_dlg.polygon(tail_poly, fill=bg_color, outline=border_color)
                    draw_dlg.line([(tail_base_x - 8, y + bubble_height - 3), (tail_base_x + 8, y + bubble_height - 3)], fill=bg_color, width=4)
                else:
                    tail_polygon = [
                        (tail_base_x - 10, y + bubble_height - 3), 
                        (tail_base_x + 10, y + bubble_height - 3), 
                        (tail_base_x - 15, y + bubble_height + 20)
                    ]
                    draw_dlg.polygon(tail_polygon, fill=bg_color, outline=border_color)
                    draw_dlg.line([(tail_base_x - 9, y + bubble_height - 3), (tail_base_x + 9, y + bubble_height - 3)], fill=bg_color, width=4)

                text_y = y + padding_y
                for line in lines:
                    line_w = draw_dlg.textbbox((0, 0), line, font=speech_font)[2] - draw_dlg.textbbox((0, 0), line, font=speech_font)[0]
                    line_x = x + (bubble_width - line_w) // 2
                    draw_dlg.text((line_x, text_y), line, font=speech_font, fill=text_fill_color)
                    text_y += line_height + 2

            final_img = Image.alpha_composite(final_img, overlay_dlg)

        # 4. Add watermark if enabled
        if watermark:
            final_img = self._add_watermark_to_pillow_image(final_img)

        return final_img
