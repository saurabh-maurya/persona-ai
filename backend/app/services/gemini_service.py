import json
from pathlib import Path
import google.generativeai as genai
from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"

_JSON_OUTPUT_OVERRIDE = """

IMPORTANT — OUTPUT FORMAT OVERRIDE:
Ignore any text/markdown output format described above.
Return ONLY a valid JSON object. No markdown fences, no extra text.

CRITICAL — DESCRIPTION LENGTH AND DETAIL REQUIREMENTS:
Every single field must be HIGHLY DETAILED and SPECIFIC. Short one-liners are NOT acceptable.
- outfitFamily: Full outfit description (3-5 sentences). Include: specific garment names, fabric/material, fit, color + shade, all visible accessories (jewelry, bag, belt, hat), shoes/footwear, hair styling, and makeup look. Example: "Fitted ivory satin slip dress with adjustable spaghetti straps and a subtle thigh-high slit. The dress skims the body closely, catching the light with a gentle sheen. Paired with strappy gold block-heeled sandals and a delicate layered gold chain necklace. Hair styled in loose beach waves falling over one shoulder. Makeup is dewy — glossy nude lip, brushed-up brows, and subtle highlighter on the cheekbones."
- lightingMood: Full lighting description (2-3 sentences). Include: light source, direction, color temperature, shadow quality, and how it falls on skin/clothing. Example: "Warm golden-hour sunlight streaming in from the left at a low 30-degree angle, casting long soft shadows across the scene. The light has a rich amber-orange hue that wraps the skin in a bronzed glow and makes the satin fabric luminous. Slight rim lighting on the shoulder from a reflective surface nearby."
- cameraStyle: Full technical shot description (2-3 sentences). Include: shot type, lens feel (focal length vibe), depth of field, any motion blur or texture. Example: "Full-length portrait shot captured with a 50mm lens at f/1.8, producing a creamy, shallow depth of field that softly blurs the background while keeping the subject razor-sharp. The camera is positioned slightly below eye level looking up, creating a flattering elongated silhouette. Natural handheld style with no harsh cropping."
- backgroundLocation: Rich scene description (3-4 sentences). Include: specific place, time of day, color palette of the environment, textures, atmospheric details, and what is visible in the blurred background. Example: "Rooftop terrace of a luxury hotel in Bandra, Mumbai, overlooking the glittering cityscape at golden hour. The terrace features weathered terracotta tiles, lush potted palms, and flickering pillar candles in amber glass holders. The blurred background reveals soft bokeh city lights beginning to twinkle as dusk settles. A warm haze gives the skyline a dream-like, cinematic quality."
- pose: Detailed full-body pose (2-3 sentences). Include: what the full body is doing, facial expression, emotional energy, eye direction. Example: "Standing tall with weight shifted slightly to the right hip, creating a subtle S-curve silhouette. Left arm hangs naturally at the side while the right hand rests lightly on the thigh. Gaze directed just past the camera with a soft, knowing smirk — relaxed confidence, not a posed smile."
- bodyAngle: Precise angle description (1-2 sentences). Example: "Three-quarter angle facing left, with the body rotated approximately 45 degrees so the right shoulder is slightly forward and the left shoulder recedes into the background."
- handPlacement: Detailed hand/arm description (1-2 sentences). Example: "Right hand lightly grazing the collarbone with fingertips, elbow bent at a natural angle. Left arm extended slightly outward with fingers loosely curled, giving a candid, mid-movement feel."
- framing: Exact framing description (1-2 sentences). Example: "Mid-shot framing from just above the knees to just above the head, with the subject centered slightly left of frame and negative space on the right."

Additionally for EACH IMAGE, generate a fullImagePrompt — a single, self-contained paragraph (5-8 sentences) that an AI image generator (Midjourney, Stable Diffusion, DALL-E) can use directly, combining all shared and individual details with the character's appearance.

Required JSON structure:
{
  "sections": [
    {
      "sectionName": "string (e.g. Morning)",
      "contentType": "Evergreen | Growth | Controversial",
      "sectionIntent": "string (2-3 sentences describing the vibe and content goal)",
      "contentSummary": "string (1-2 sentences summarizing what was created for sequel context)",
      "sharedDescription": {
        "outfitFamily": "string (detailed outfit — see requirements above)",
        "lightingMood": "string (detailed lighting — see requirements above)",
        "cameraStyle": "string (detailed camera — see requirements above)",
        "backgroundLocation": "string (detailed scene — see requirements above)"
      },
      "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#fyp"],
      "imageDescriptions": [
        {
          "imageNo": 1,
          "pose": "string (detailed — see requirements above)",
          "bodyAngle": "string (detailed — see requirements above)",
          "handPlacement": "string (detailed — see requirements above)",
          "framing": "string (detailed — see requirements above)",
          "fullImagePrompt": "string (complete self-contained AI image prompt combining character appearance, outfit, lighting, location, and this specific pose/angle/framing)"
        }
      ]
    }
  ]
}"""


def _load_prompt(filename: str) -> str:
    path = _PROMPTS_DIR / filename
    return path.read_text() if path.exists() else ""


class GeminiService:
    def __init__(self):
        settings = get_settings()
        self._settings = settings
        self._provider = None

        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            self.model = genai.GenerativeModel(settings.gemini_model)
            self._provider = "gemini"
            logger.info("ai_provider", provider="gemini", model=settings.gemini_model)
        elif settings.groq_api_key:
            from groq import AsyncGroq
            self._groq_client = AsyncGroq(api_key=settings.groq_api_key)
            self._provider = "groq"
            logger.info("ai_provider", provider="groq", model=settings.groq_model)
        else:
            raise RuntimeError("No AI provider configured. Set GEMINI_API_KEY or GROQ_API_KEY in .env")

    async def _generate(self, prompt: str) -> str:
        if self._provider == "groq":
            return await self._groq_generate(prompt, json_mode=True)
        else:
            try:
                response = await self.model.generate_content_async(prompt)
                return response.text
            except Exception as e:
                # Fall back to Groq if Gemini key is invalid/expired
                if hasattr(self._settings, 'groq_api_key') and self._settings.groq_api_key:
                    logger.warning("gemini_failed_falling_back_to_groq", error=str(e)[:100])
                    from groq import AsyncGroq
                    self._groq_client = AsyncGroq(api_key=self._settings.groq_api_key)
                    return await self._groq_generate(prompt, json_mode=True)
                raise

    async def _groq_generate(self, prompt: str, json_mode: bool = False) -> str:
        model = self._settings.groq_model
        # only use json_mode for models known to handle it reliably
        supports_json_mode = not any(x in model for x in ("gemma", "qwen", "llama-4"))
        kwargs: dict = dict(
            model=model,
            messages=[
                {"role": "system", "content": "You are a content generation assistant. Always return valid JSON when requested."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=8000,
        )
        if json_mode and supports_json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = await self._groq_client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def _extract_json(self, text: str) -> dict | list:
        """Strip markdown fences, then extract first valid JSON object/array."""
        text = text.strip()
        # Strip markdown code fences
        if text.startswith("```"):
            lines = text.split("\n")
            inner = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
            text = inner.strip()
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Find the outermost { ... } or [ ... ] and try that
        start = next((i for i, c in enumerate(text) if c in '{['), None)
        if start is not None:
            opener = text[start]
            closer = '}' if opener == '{' else ']'
            depth = 0
            for i, c in enumerate(text[start:], start):
                if c == opener:
                    depth += 1
                elif c == closer:
                    depth -= 1
                    if depth == 0:
                        return json.loads(text[start:i+1])
        raise ValueError(f"No valid JSON found in response (length {len(text)})")

    def _build_character_profile(self, character: dict) -> str:
        def _trim(s, n=150): return (s or '')[:n]
        return f"""Name: {character['name']}
Age: {_trim(character.get('age',''), 30)} | Gender: {_trim(character.get('gender',''), 60)}
Niche: {_trim(character.get('niche',''), 80)} | Location: {character.get('city','')}, {character.get('country','')}
Personality: {_trim(character.get('persona',''), 120)}
Appearance: {_trim(character.get('appearance',''), 200)}
Fashion: {_trim(character.get('fashionStyle',''), 120)}"""

    async def generate_single_section(
        self,
        character: dict,
        day_no: int,
        date_str: str,
        section: dict,
        content_summary: str,
        previous_summaries: list[str],
    ) -> dict:
        """Generate one section (Morning/Evening/Night) for a single day."""
        master_prompt = _load_prompt("master_image_description.md")
        if character.get("masterPrompt"):
            master_prompt = character["masterPrompt"] + _JSON_OUTPUT_OVERRIDE
        else:
            master_prompt = master_prompt + _JSON_OUTPUT_OVERRIDE

        character_profile = self._build_character_profile(character)

        prev_context = ""
        if previous_summaries:
            prev_context = "Previous batch content (avoid repeating themes/outfits/locations):\n" + \
                           "\n".join(f"- {s}" for s in previous_summaries[:5])

        batch_context = f"Batch theme / sequel context: {content_summary}" if content_summary else ""
        section_text = f"{section['name']}: {section['imageCount']} images"

        prompt = f"""{master_prompt}

Number of Days: 1
Dates: {date_str}
Sections per day: {section_text}
{batch_context}
{prev_context}

Character Profile:
{character_profile}"""

        raw = await self._generate(prompt)
        return self._extract_json(raw)

    async def ping(self) -> dict:
        """Minimal connectivity test — 1-word prompt, returns provider/latency."""
        import time
        start = time.time()
        if self._provider == "groq":
            resp = await self._groq_client.chat.completions.create(
                model=self._settings.groq_model,
                messages=[{"role": "user", "content": "Reply with one word: OK"}],
                max_tokens=5,
                temperature=0,
            )
            text = resp.choices[0].message.content.strip()
            model = self._settings.groq_model
        else:
            try:
                response = await self.model.generate_content_async("Reply with one word: OK")
                text = response.text.strip()
                model = self._settings.gemini_model
            except Exception as e:
                # Gemini key invalid — fall back to Groq for ping too
                if self._settings.groq_api_key:
                    from groq import AsyncGroq
                    if not hasattr(self, '_groq_client'):
                        self._groq_client = AsyncGroq(api_key=self._settings.groq_api_key)
                    resp = await self._groq_client.chat.completions.create(
                        model=self._settings.groq_model,
                        messages=[{"role": "user", "content": "Reply with one word: OK"}],
                        max_tokens=5,
                        temperature=0,
                    )
                    text = resp.choices[0].message.content.strip()
                    model = self._settings.groq_model
                else:
                    raise
        return {
            "provider": self._provider,
            "model": model,
            "latency_ms": round((time.time() - start) * 1000),
            "response": text[:20],
        }

    async def generate_character(self, name: str, niche: str, vibe: str, location: str) -> dict:
        prompt_template = _load_prompt("character_generation.md")
        prompt = prompt_template.replace("{name}", name).replace("{niche}", niche) \
                                .replace("{vibe}", vibe).replace("{location}", location)

        logger.info("generating_character", name=name, provider=self._provider)
        raw = await self._generate(prompt)
        return self._extract_json(raw)
