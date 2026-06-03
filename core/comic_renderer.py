import os
from PIL import Image, ImageDraw, ImageFont
from config import settings

class ComicRenderer:
    def __init__(self):
        # We try to use a standard font, fallback to default if not found
        self.font_path = self._get_default_font()
        
    def _get_default_font(self):
        # Try to find a standard Windows font (Arial)
        windows_font = "C:\\Windows\\Fonts\\arialbd.ttf" # Bold font looks better for comics
        if not os.path.exists(windows_font):
            windows_font = "C:\\Windows\\Fonts\\arial.ttf"
        if os.path.exists(windows_font):
            return windows_font
        return None

    def _wrap_text(self, text: str, font, max_width: int, draw: ImageDraw) -> list:
        lines = []
        for manual_line in text.split('\n'):
            words = manual_line.split()
            current_line = []
            
            for word in words:
                current_line.append(word)
                bbox = draw.textbbox((0, 0), " ".join(current_line), font=font)
                if bbox[2] - bbox[0] > max_width:
                    current_line.pop()
                    if current_line:
                        lines.append(" ".join(current_line))
                    current_line = [word]
            if current_line:
                lines.append(" ".join(current_line))
        return lines

    def draw_speech_bubble(self, image_path: str, dialogues: list, output_path: str):
        """Draws professional manga-style speech bubbles and narration boxes."""
        if not dialogues:
            return image_path
            
        try:
            img = Image.open(image_path).convert("RGBA")
            overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(overlay)
            
            if self.font_path:
                try:
                    font = ImageFont.truetype(self.font_path, 16)
                except IOError:
                    font = ImageFont.load_default()
            else:
                font = ImageFont.load_default()
                
            y_offset = 20
            # Alternate positions to simulate comic flow
            positions = ['top-left', 'bottom-right', 'top-right', 'bottom-left']
            
            for i, dialogue in enumerate(dialogues):
                pos = positions[i % len(positions)]
                
                speaker = str(dialogue.get("speaker", "Unknown")).strip()
                dlg_type = str(dialogue.get("type", "speech")).lower()
                
                # Format and clean text
                raw_text = dialogue.get('text', '').strip()
                
                # Strip character name prefixes (e.g., "new apprentice / Yes", "old mage: Can you...")
                if speaker:
                    spk_clean = speaker.lower()
                    for sep in ["/", ":", "-", "—"]:
                        for pattern in [f"{spk_clean}{sep}", f"{spk_clean} {sep}"]:
                            if raw_text.lower().startswith(pattern):
                                raw_text = raw_text[len(pattern):].strip()
                        # Also strip general matches
                        if sep in raw_text:
                            parts = raw_text.split(sep, 1)
                            if parts[0].strip().lower() == spk_clean:
                                raw_text = parts[1].strip()
                                
                # General clean up of leading/trailing punctuation and quotes
                while raw_text.startswith(':') or raw_text.startswith('/') or raw_text.startswith('-') or raw_text.startswith('"') or raw_text.startswith("'"):
                    raw_text = raw_text[1:].strip()
                while raw_text.endswith('"') or raw_text.endswith("'"):
                    raw_text = raw_text[:-1].strip()
                
                # Join fragmented lines (replace newlines or multiple spaces with a single space)
                raw_text = " ".join(raw_text.split())

                if dlg_type == "narration" or speaker.lower() == "narrator":
                    text = raw_text
                    is_narration = True
                else:
                    # Strip any lingering "speaker / " prefixes inside the bubble text
                    text = raw_text
                    is_narration = False
                
                # Wrap Text
                max_width = 220 if is_narration else 180
                lines = self._wrap_text(text, font, max_width, draw)
                
                if not lines:
                    continue
                    
                line_height = draw.textbbox((0, 0), lines[0], font=font)[3] - draw.textbbox((0, 0), lines[0], font=font)[1]
                text_width = max([draw.textbbox((0, 0), line, font=font)[2] - draw.textbbox((0, 0), line, font=font)[0] for line in lines])
                
                padding_x = 25
                padding_y = 20
                bubble_width = text_width + (padding_x * 2)
                bubble_height = (line_height * len(lines)) + (padding_y * 2) + (len(lines) * 4)
                
                # Calculate Coordinates based on position
                if pos.startswith('top'):
                    y = y_offset
                    y_offset += bubble_height + 40
                else:
                    y = img.height - bubble_height - 30
                    
                if pos.endswith('left'):
                    x = 20
                else:
                    x = img.width - bubble_width - 20
                
                # Ensure it doesn't go out of bounds
                x = max(10, min(x, img.width - bubble_width - 10))
                y = max(10, min(y, img.height - bubble_height - 10))
                
                if is_narration:
                    # NARRATION BOX (Rectangular, black/dark background, white text)
                    box_fill = (20, 20, 20, 230)
                    text_fill = (255, 255, 255, 255)
                    outline_fill = (255, 255, 255, 200)
                    
                    # Draw Box
                    draw.rectangle([x, y, x + bubble_width, y + bubble_height], fill=box_fill, outline=outline_fill, width=2)
                    
                else:
                    # SPEECH BUBBLE (Rounded, white background, black text, with tail)
                    box_fill = (255, 255, 255, 245)
                    text_fill = (0, 0, 0, 255)
                    outline_fill = (0, 0, 0, 255)
                    shadow_fill = (0, 0, 0, 100)
                    
                    # Draw drop shadow
                    draw.rounded_rectangle([x + 4, y + 4, x + bubble_width + 4, y + bubble_height + 4], radius=15, fill=shadow_fill)
                    
                    # Draw Bubble
                    draw.rounded_rectangle([x, y, x + bubble_width, y + bubble_height], radius=15, fill=box_fill, outline=outline_fill, width=3)
                    
                    # Draw Tail (Dynamic based on position)
                    tail_base_x = x + (bubble_width // 2)
                    if pos.startswith('top'):
                        # Tail points down
                        tail_tip_y = y + bubble_height + 30
                        tail_polygon = [(tail_base_x - 10, y + bubble_height - 3), (tail_base_x + 10, y + bubble_height - 3), (tail_base_x - 15, tail_tip_y)]
                        draw.polygon(tail_polygon, fill=box_fill, outline=outline_fill)
                        draw.line([(tail_base_x - 9, y + bubble_height - 3), (tail_base_x + 9, y + bubble_height - 3)], fill=box_fill, width=4)
                    else:
                        # Tail points up
                        tail_tip_y = y - 30
                        tail_polygon = [(tail_base_x - 10, y + 3), (tail_base_x + 10, y + 3), (tail_base_x + 15, tail_tip_y)]
                        draw.polygon(tail_polygon, fill=box_fill, outline=outline_fill)
                        draw.line([(tail_base_x - 9, y + 3), (tail_base_x + 9, y + 3)], fill=box_fill, width=4)
                
                # Draw Text
                text_y = y + padding_y
                for line in lines:
                    line_w = draw.textbbox((0, 0), line, font=font)[2] - draw.textbbox((0, 0), line, font=font)[0]
                    # Center text
                    line_x = x + (bubble_width - line_w) // 2
                    draw.text((line_x, text_y), line, font=font, fill=text_fill)
                    text_y += line_height + 2
                
            # Combine the overlay with the original image
            final_img = Image.alpha_composite(img, overlay).convert("RGB")
            final_img.save(output_path)
            return output_path
            
        except Exception as e:
            print(f"Error drawing speech bubble: {e}")
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
                font = ImageFont.load_default()
        else:
            font = ImageFont.load_default()
            
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
                
                # Resize image to panel dimensions
                resized_img = img.resize((panel.width, panel.height), Image.Resampling.LANCZOS)
                
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
