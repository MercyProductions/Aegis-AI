from __future__ import annotations

import colorsys
import json
import math
import re
import shutil
import struct
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # pragma: no cover - exercised only when Pillow is unavailable
    Image = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]
    ImageFont = None  # type: ignore[assignment]

from .schemas import MediaAsset, MediaCapabilitiesResponse, MediaCreativeRequest, MediaJobResponse
from .settings import Settings


SUPPORTED_KINDS = [
    "image",
    "video",
    "animation",
    "gif",
    "video_edit",
    "music_beat",
    "psd_template",
    "brand_kit",
    "thumbnail",
    "icon_set",
    "sticker_pack",
]


@dataclass(frozen=True)
class Theme:
    primary: str
    palette: list[str]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str, fallback: str = "creative-job") -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return (slug or fallback)[:54]


def normalize_hex(value: str) -> str:
    raw = value.strip().lower()
    named = {
        "green": "#26dd7b",
        "aegis": "#26dd7b",
        "gold": "#d7a84f",
        "blue": "#4f8cff",
        "purple": "#9d6cff",
        "red": "#ef4444",
        "pink": "#ec4899",
        "orange": "#f97316",
        "teal": "#14b8a6",
        "white": "#f8fafc",
        "black": "#05080d",
    }
    raw = named.get(raw, raw)
    if re.fullmatch(r"#[0-9a-f]{6}", raw):
        return raw
    if re.fullmatch(r"[0-9a-f]{6}", raw):
        return f"#{raw}"
    if re.fullmatch(r"#[0-9a-f]{3}", raw):
        return "#" + "".join(ch * 2 for ch in raw[1:])
    return ""


def infer_theme_color(prompt: str, explicit: str = "") -> str:
    explicit_color = normalize_hex(explicit)
    if explicit_color:
        return explicit_color

    text = prompt.lower()
    keyword_colors = [
        (("#", "aegis", "security", "finance", "growth", "eco", "money", "trading"), "#26dd7b"),
        (("luxury", "premium", "gold", "royal", "wealth"), "#d7a84f"),
        (("calm", "medical", "health", "trust", "water", "ocean"), "#14b8a6"),
        (("sports", "energy", "fitness", "speed", "hype"), "#f97316"),
        (("cyber", "sci-fi", "gaming", "neon", "future"), "#9d6cff"),
        (("corporate", "clean", "saas", "productivity", "cloud"), "#4f8cff"),
        (("romantic", "beauty", "fashion", "valentine"), "#ec4899"),
        (("urgent", "warning", "alert", "sale"), "#ef4444"),
    ]
    for keywords, color in keyword_colors:
        if any(keyword in text for keyword in keywords):
            return color
    return "#26dd7b"


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = normalize_hex(value) or "#26dd7b"
    return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*[max(0, min(255, channel)) for channel in rgb])


def build_palette(primary: str) -> list[str]:
    r, g, b = hex_to_rgb(primary)
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)

    def variant(hue_shift: float, lightness: float, saturation: float) -> str:
        rr, gg, bb = colorsys.hls_to_rgb((h + hue_shift) % 1.0, lightness, saturation)
        return rgb_to_hex((int(rr * 255), int(gg * 255), int(bb * 255)))

    return [
        primary,
        variant(0.0, min(0.72, l + 0.18), min(1.0, s + 0.08)),
        variant(0.08, max(0.28, l - 0.08), min(1.0, s + 0.02)),
        variant(0.50, max(0.38, l + 0.04), max(0.45, s * 0.72)),
        "#05080d",
        "#f8fafc",
    ]


def best_output_formats(kind: str, requested: list[str]) -> list[str]:
    if requested:
        return [item.strip().lower().lstrip(".") for item in requested if item.strip()]
    defaults = {
        "image": ["png", "svg"],
        "thumbnail": ["png", "svg"],
        "brand_kit": ["png", "svg", "json"],
        "icon_set": ["png", "svg", "json"],
        "sticker_pack": ["png", "svg", "gif"],
        "gif": ["gif", "png", "svg"],
        "animation": ["html", "svg", "gif"],
        "video": ["html", "png"],
        "video_edit": ["json", "html", "md"],
        "music_beat": ["wav", "json", "md"],
        "psd_template": ["psd", "jsx", "png", "json"],
    }
    return defaults.get(kind, ["png", "svg"])


def safe_title(prompt: str) -> str:
    title = re.sub(r"\s+", " ", prompt.strip()).strip()
    if not title:
        return "Aegis Creative"
    return title[:72]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def write_flat_psd(path: Path, image: Any) -> None:
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.tobytes()
    channels = [
        pixels[0::3],
        pixels[1::3],
        pixels[2::3],
    ]
    with path.open("wb") as handle:
        handle.write(b"8BPS")
        handle.write(struct.pack(">H", 1))
        handle.write(b"\0" * 6)
        handle.write(struct.pack(">H", 3))
        handle.write(struct.pack(">I", height))
        handle.write(struct.pack(">I", width))
        handle.write(struct.pack(">H", 8))
        handle.write(struct.pack(">H", 3))
        handle.write(struct.pack(">I", 0))  # color mode data
        handle.write(struct.pack(">I", 0))  # image resources
        handle.write(struct.pack(">I", 0))  # layer and mask info
        handle.write(struct.pack(">H", 0))  # raw image data
        for channel in channels:
            handle.write(channel)


class CreativeMediaEngine:
    def __init__(self, project_root: Path, settings: Settings):
        self.project_root = project_root
        self.settings = settings
        self.base_dir = project_root / "workspace" / "creative_media"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def capabilities(self) -> MediaCapabilitiesResponse:
        pillow_ready = Image is not None
        ffmpeg_ready = shutil.which("ffmpeg") is not None
        return MediaCapabilitiesResponse(
            supported_kinds=SUPPORTED_KINDS,  # type: ignore[arg-type]
            local_formats=["png", "svg", "gif", "html", "jsx", "psd", "json", "wav"] if pillow_ready else ["svg", "html", "jsx", "json", "wav"],
            provider_formats=["png", "jpg", "webp", "gif", "mp4", "webm", "svg", "psd-package", "wav", "mp3", "midi", "stems"],
            can_iterate_from_previous=True,
            theme_inference=True,
            psd_template_strategy=(
                "Creates a flattened PSD preview plus a Photoshop JSX script and layer manifest for rebuilding editable layers."
            ),
            local_renderers={
                "pillow": pillow_ready,
                "ffmpeg": ffmpeg_ready,
                "svg": True,
                "html_animation": True,
                "photoshop_jsx": True,
                "wav_preview": True,
                "video_edit_manifest": True,
            },
            recommendations=[
                "Use a persistent media job id for feedback-driven revisions.",
                "Keep source prompts, layer specs, palettes, frames, and provider metadata with every asset.",
                "Add cloud provider adapters later for photoreal image, video, and music generation while preserving the local editable package.",
            ],
        )

    def create_job(self, request: MediaCreativeRequest) -> MediaJobResponse:
        theme = Theme(
            primary=infer_theme_color(f"{request.prompt} {request.style}", request.theme_color),
            palette=[],
        )
        theme = Theme(primary=theme.primary, palette=build_palette(theme.primary))
        job_id = f"{slugify(request.kind)}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}"
        job_dir = self.base_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        previous_manifest = self._load_previous_manifest(request.previous_job_id)
        effective_prompt = self._compose_effective_prompt(request, previous_manifest)
        formats = best_output_formats(request.kind, request.output_formats)

        assets: list[MediaAsset] = []
        warnings: list[str] = []

        assets.extend(self._write_brief_assets(job_dir, request, effective_prompt, theme, formats, previous_manifest))
        svg_path = self._write_svg_template(job_dir, request, effective_prompt, theme)
        assets.append(self._asset(svg_path, request.kind, "svg", "editable vector template", "image/svg+xml", True))

        if request.kind == "music_beat":
            assets.extend(self._write_music_assets(job_dir, request, effective_prompt, theme))

        if request.kind == "video_edit":
            assets.extend(self._write_video_edit_assets(job_dir, request, effective_prompt, theme))

        if Image is None:
            warnings.append("Pillow is not available, so raster PNG/GIF/PSD preview rendering was skipped.")
        else:
            preview_path = self._write_png_preview(job_dir, request, effective_prompt, theme)
            assets.append(self._asset(preview_path, request.kind, "png", "raster preview", "image/png", True))

            if request.kind in {"gif", "animation", "video", "video_edit", "sticker_pack"} or "gif" in formats:
                gif_path = self._write_gif_preview(job_dir, request, effective_prompt, theme)
                assets.append(self._asset(gif_path, request.kind, "gif", "motion preview", "image/gif", True, preview_path.name))

            if request.kind == "psd_template" or "psd" in formats:
                psd_path = job_dir / "template_flat_preview.psd"
                image = self._make_preview_image(request, effective_prompt, theme)
                write_flat_psd(psd_path, image)
                assets.append(self._asset(psd_path, request.kind, "psd", "flat Photoshop preview", "image/vnd.adobe.photoshop", True, "layer_manifest.json"))

        if request.kind in {"animation", "video", "video_edit", "gif"} or "html" in formats:
            html_path = self._write_animation_html(job_dir, request, effective_prompt, theme)
            assets.append(self._asset(html_path, request.kind, "html", "editable motion storyboard", "text/html", True))

        if request.kind in {"video", "video_edit"} and shutil.which("ffmpeg") is None:
            warnings.append("ffmpeg is not installed, so this slice creates storyboard frames/HTML instead of MP4/WebM video.")

        jsx_path = self._write_photoshop_jsx(job_dir, request, effective_prompt, theme)
        if request.kind == "psd_template" or "jsx" in formats:
            assets.append(self._asset(jsx_path, request.kind, "jsx", "Photoshop layer builder", "text/javascript", True))

        response = MediaJobResponse(
            id=job_id,
            created_at=utc_now(),
            kind=request.kind,
            status="ready",
            prompt=request.prompt,
            feedback=request.feedback,
            previous_job_id=request.previous_job_id,
            theme_color=theme.primary,
            palette=theme.palette,
            aspect_ratio=request.aspect_ratio,
            style=request.style,
            plan=self._plan_for(request.kind),
            assets=assets,
            warnings=warnings,
            next_actions=[
                "Send feedback with previous_job_id to revise without losing the current package.",
                "Use theme_color to override the inferred palette.",
                "Connect a provider adapter for photoreal image/video generation while keeping these editable source files.",
            ],
            job_dir=str(job_dir),
        )
        write_json(job_dir / "manifest.json", response.model_dump())
        return response

    def list_jobs(self, limit: int = 50, kind: str = "") -> list[MediaJobResponse]:
        requested_kind = kind.strip()
        jobs: list[MediaJobResponse] = []
        for manifest_path in self.base_dir.glob("*/manifest.json"):
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                job = MediaJobResponse.model_validate(payload)
            except Exception:
                continue
            if requested_kind and job.kind != requested_kind:
                continue
            jobs.append(job)
        jobs.sort(key=lambda item: item.created_at, reverse=True)
        return jobs[: max(1, min(200, limit))]

    def get_job(self, job_id: str) -> MediaJobResponse:
        manifest_path = self._job_manifest_path(job_id)
        if manifest_path is None or not manifest_path.exists():
            raise FileNotFoundError(job_id)
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        return MediaJobResponse.model_validate(payload)

    def _job_manifest_path(self, job_id: str) -> Path | None:
        safe_id = job_id.strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,96}", safe_id):
            return None
        manifest_path = (self.base_dir / safe_id / "manifest.json").resolve()
        try:
            manifest_path.relative_to(self.base_dir.resolve())
        except ValueError:
            return None
        return manifest_path

    def _load_previous_manifest(self, previous_job_id: str) -> dict[str, Any] | None:
        if not previous_job_id.strip():
            return None
        safe_id = slugify(previous_job_id, "")
        if safe_id != previous_job_id:
            return None
        manifest_path = self.base_dir / previous_job_id / "manifest.json"
        if not manifest_path.exists():
            return None
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def _compose_effective_prompt(self, request: MediaCreativeRequest, previous: dict[str, Any] | None) -> str:
        if previous is None:
            return request.prompt
        feedback = request.feedback.strip() or request.prompt.strip()
        return "\n".join(
            [
                f"Original prompt: {previous.get('prompt', '')}",
                f"Previous theme: {previous.get('theme_color', '')}",
                f"Revision feedback: {feedback}",
                "Preserve useful composition, palette, layer names, and motion beats unless the feedback conflicts.",
            ]
        )

    def _write_brief_assets(
        self,
        job_dir: Path,
        request: MediaCreativeRequest,
        effective_prompt: str,
        theme: Theme,
        formats: list[str],
        previous: dict[str, Any] | None,
    ) -> list[MediaAsset]:
        prompt_pack = {
            "kind": request.kind,
            "prompt": request.prompt,
            "effective_prompt": effective_prompt,
            "feedback": request.feedback,
            "previous_job_id": request.previous_job_id,
            "theme_color": theme.primary,
            "palette": theme.palette,
            "aspect_ratio": request.aspect_ratio,
            "style": request.style,
            "duration_seconds": request.duration_seconds,
            "fps": request.fps,
            "output_formats": formats,
            "provider_prompts": {
                "image": f"{effective_prompt}\nTheme color {theme.primary}. High-end finished composition. Editable layout intent.",
                "video": f"{effective_prompt}\nCreate a {request.duration_seconds:.1f}s cinematic motion sequence with coherent continuity.",
                "video_edit": f"{effective_prompt}\nCreate an edit plan with cuts, transitions, pacing notes, captions, sound design, and export targets.",
                "animation": f"{effective_prompt}\nLoopable motion, clean timing, reusable vector layers.",
                "music_beat": f"{effective_prompt}\nCreate a beat arrangement with BPM, key, drums, bass, melody, mix notes, and revision-friendly stems.",
                "psd": f"{effective_prompt}\nBuild as editable Photoshop layers with named groups, smart-object placeholders, and safe margins.",
            },
            "previous_summary": previous,
        }
        brief = [
            "# Aegis Creative Media Brief",
            "",
            f"- Kind: {request.kind}",
            f"- Prompt: {request.prompt}",
            f"- Feedback: {request.feedback or 'none'}",
            f"- Previous job: {request.previous_job_id or 'none'}",
            f"- Theme color: {theme.primary}",
            f"- Palette: {', '.join(theme.palette)}",
            f"- Aspect ratio: {request.aspect_ratio}",
            f"- Style: {request.style or 'inferred'}",
            "",
            "## Effective Prompt",
            "",
            effective_prompt,
            "",
            "## Revision Strategy",
            "",
            "Keep the manifest, prompt pack, layer spec, and source templates with the job so feedback can revise the same creative direction instead of restarting.",
        ]
        prompt_pack_path = job_dir / "prompt_pack.json"
        brief_path = job_dir / "creative_brief.md"
        layer_path = job_dir / "layer_manifest.json"
        write_json(prompt_pack_path, prompt_pack)
        brief_path.write_text("\n".join(brief), encoding="utf-8")
        write_json(
            layer_path,
            {
                "canvas": {"width": request.width, "height": request.height, "aspect_ratio": request.aspect_ratio},
                "theme": {"primary": theme.primary, "palette": theme.palette},
                "layers": [
                    {"name": "Background / gradient field", "type": "shape", "editable": True},
                    {"name": "Accent energy lines", "type": "shape", "editable": True},
                    {"name": "Hero focal object", "type": "shape_or_smart_object", "editable": True},
                    {"name": "Headline / safe text area", "type": "text", "editable": True},
                    {"name": "CTA / detail band", "type": "text_shape_group", "editable": True},
                ],
                "music_layers": [
                    {"name": "Drums", "type": "pattern", "editable": True},
                    {"name": "Bass", "type": "melody", "editable": True},
                    {"name": "Chords", "type": "harmony", "editable": True},
                    {"name": "Lead", "type": "melody", "editable": True},
                    {"name": "FX and transitions", "type": "automation", "editable": True},
                ],
            },
        )
        return [
            self._asset(brief_path, request.kind, "md", "creative brief", "text/markdown", True),
            self._asset(prompt_pack_path, request.kind, "json", "provider prompt pack", "application/json", True),
            self._asset(layer_path, request.kind, "json", "editable layer manifest", "application/json", True),
        ]

    def _write_svg_template(self, job_dir: Path, request: MediaCreativeRequest, prompt: str, theme: Theme) -> Path:
        title = safe_title(prompt)
        width = request.width
        height = request.height
        p0, p1, p2, p3, dark, light = theme.palette
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{dark}"/>
      <stop offset="0.48" stop-color="#0d1520"/>
      <stop offset="1" stop-color="{p2}"/>
    </linearGradient>
    <radialGradient id="glow" cx="38%" cy="34%" r="50%">
      <stop offset="0" stop-color="{p0}" stop-opacity="0.42"/>
      <stop offset="1" stop-color="{p0}" stop-opacity="0"/>
    </radialGradient>
    <filter id="softShadow"><feDropShadow dx="0" dy="18" stdDeviation="20" flood-color="#000" flood-opacity="0.32"/></filter>
  </defs>
  <rect width="{width}" height="{height}" fill="url(#bg)"/>
  <rect width="{width}" height="{height}" fill="url(#glow)"/>
  <g opacity="0.18">
    <path d="M {-width * 0.10:.0f} {height * 0.82:.0f} C {width * 0.18:.0f} {height * 0.50:.0f}, {width * 0.55:.0f} {height * 1.02:.0f}, {width * 1.12:.0f} {height * 0.20:.0f}" stroke="{p1}" stroke-width="3" fill="none"/>
    <path d="M {-width * 0.02:.0f} {height * 0.62:.0f} C {width * 0.30:.0f} {height * 0.18:.0f}, {width * 0.60:.0f} {height * 0.92:.0f}, {width * 1.04:.0f} {height * 0.10:.0f}" stroke="{p3}" stroke-width="2" fill="none"/>
  </g>
  <g filter="url(#softShadow)">
    <rect x="{width * 0.12:.0f}" y="{height * 0.18:.0f}" width="{width * 0.76:.0f}" height="{height * 0.58:.0f}" rx="34" fill="#101923" opacity="0.86" stroke="{p0}" stroke-opacity="0.46"/>
    <circle cx="{width * 0.70:.0f}" cy="{height * 0.33:.0f}" r="{min(width, height) * 0.14:.0f}" fill="{p0}" opacity="0.22"/>
    <circle cx="{width * 0.76:.0f}" cy="{height * 0.43:.0f}" r="{min(width, height) * 0.08:.0f}" fill="{p3}" opacity="0.18"/>
  </g>
  <text x="{width * 0.17:.0f}" y="{height * 0.39:.0f}" fill="{light}" font-family="Segoe UI, Arial, sans-serif" font-size="{max(34, width // 25)}" font-weight="700">{title}</text>
  <text x="{width * 0.17:.0f}" y="{height * 0.48:.0f}" fill="{p1}" font-family="Segoe UI, Arial, sans-serif" font-size="{max(18, width // 55)}">Generated by Aegis Creative Studio</text>
  <rect x="{width * 0.17:.0f}" y="{height * 0.57:.0f}" width="{width * 0.22:.0f}" height="{height * 0.07:.0f}" rx="18" fill="{p0}"/>
  <text x="{width * 0.20:.0f}" y="{height * 0.615:.0f}" fill="#04100a" font-family="Segoe UI, Arial, sans-serif" font-size="{max(16, width // 70)}" font-weight="700">EDITABLE TEMPLATE</text>
</svg>
"""
        path = job_dir / "template.svg"
        path.write_text(svg, encoding="utf-8")
        return path

    def _make_preview_image(self, request: MediaCreativeRequest, prompt: str, theme: Theme) -> Any:
        if Image is None or ImageDraw is None:
            raise RuntimeError("Pillow is not available")
        width = request.width
        height = request.height
        p0 = hex_to_rgb(theme.palette[0])
        p2 = hex_to_rgb(theme.palette[2])
        p3 = hex_to_rgb(theme.palette[3])
        image = Image.new("RGB", (width, height), hex_to_rgb("#05080d"))
        draw = ImageDraw.Draw(image, "RGBA")
        for y in range(height):
            t = y / max(1, height - 1)
            color = (
                int(5 * (1 - t) + p2[0] * t * 0.55),
                int(8 * (1 - t) + p2[1] * t * 0.55),
                int(13 * (1 - t) + p2[2] * t * 0.55),
            )
            draw.line([(0, y), (width, y)], fill=color)
        draw.ellipse((int(width * 0.55), int(height * 0.06), int(width * 1.02), int(height * 0.74)), fill=(*p0, 42))
        draw.ellipse((int(width * -0.08), int(height * 0.38), int(width * 0.36), int(height * 1.05)), fill=(*p3, 28))
        draw.rounded_rectangle((int(width * 0.11), int(height * 0.17), int(width * 0.89), int(height * 0.78)), radius=34, fill=(16, 25, 35, 226), outline=(*p0, 120), width=2)
        for i in range(10):
            x = int(width * (0.13 + i * 0.078))
            draw.line((x, int(height * 0.18), x + int(width * 0.26), int(height * 0.78)), fill=(*p0, 18), width=1)
        title = safe_title(prompt)
        font = ImageFont.load_default() if ImageFont is not None else None
        draw.text((int(width * 0.17), int(height * 0.36)), title, fill=(248, 250, 252, 255), font=font)
        draw.text((int(width * 0.17), int(height * 0.45)), "Aegis Creative Studio", fill=(*p0, 255), font=font)
        draw.rounded_rectangle((int(width * 0.17), int(height * 0.58), int(width * 0.40), int(height * 0.66)), radius=18, fill=(*p0, 255))
        draw.text((int(width * 0.20), int(height * 0.61)), "EDITABLE", fill=(3, 16, 10, 255), font=font)
        return image

    def _write_png_preview(self, job_dir: Path, request: MediaCreativeRequest, prompt: str, theme: Theme) -> Path:
        path = job_dir / "preview.png"
        self._make_preview_image(request, prompt, theme).save(path)
        return path

    def _write_gif_preview(self, job_dir: Path, request: MediaCreativeRequest, prompt: str, theme: Theme) -> Path:
        if Image is None or ImageDraw is None:
            raise RuntimeError("Pillow is not available")
        scale = min(1.0, 640.0 / request.width, 360.0 / request.height)
        preview_request = request.model_copy(
            update={
                "width": max(256, int(request.width * scale)),
                "height": max(256, int(request.height * scale)),
            }
        )
        frame_count = max(8, min(32, int(request.duration_seconds * min(request.fps, 10))))
        frames = []
        p0 = hex_to_rgb(theme.palette[0])
        p3 = hex_to_rgb(theme.palette[3])
        for i in range(frame_count):
            frame = self._make_preview_image(preview_request, prompt, theme).convert("RGBA")
            draw = ImageDraw.Draw(frame, "RGBA")
            phase = i / frame_count
            x = int((preview_request.width + 180) * phase) - 90
            draw.rounded_rectangle((x, int(preview_request.height * 0.16), x + 90, int(preview_request.height * 0.78)), radius=20, fill=(*p0, 34))
            draw.ellipse(
                (
                    int(preview_request.width * (0.62 + 0.08 * phase)),
                    int(preview_request.height * 0.24),
                    int(preview_request.width * (0.80 + 0.08 * phase)),
                    int(preview_request.height * 0.50),
                ),
                fill=(*p3, 44),
            )
            frames.append(frame.convert("P", palette=Image.Palette.ADAPTIVE))
        path = job_dir / "motion_preview.gif"
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=max(30, int(1000 / max(1, request.fps))), loop=0)
        return path

    def _write_animation_html(self, job_dir: Path, request: MediaCreativeRequest, prompt: str, theme: Theme) -> Path:
        title = safe_title(prompt)
        p0, p1, p2, p3, dark, light = theme.palette
        html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
html,body{{margin:0;width:100%;height:100%;background:{dark};display:grid;place-items:center;overflow:hidden;font-family:Segoe UI,Arial,sans-serif;}}
.stage{{width:min(100vw,{request.width}px);aspect-ratio:{request.width}/{request.height};position:relative;overflow:hidden;background:linear-gradient(135deg,{dark},#0d1520,{p2});}}
.glow{{position:absolute;inset:8%;border-radius:40px;background:radial-gradient(circle at 70% 35%,{p0}55,transparent 34%),rgba(16,25,35,.84);border:1px solid {p0}77;box-shadow:0 35px 80px #0009;}}
.beam{{position:absolute;inset:-20%;background:linear-gradient(105deg,transparent 0 45%,#ffffff22 50%,transparent 56%);animation:sweep {max(2.4, request.duration_seconds / 1.5):.2f}s linear infinite;}}
.orb{{position:absolute;width:18%;aspect-ratio:1;border-radius:50%;background:{p3}44;right:18%;top:22%;animation:float {max(2.8, request.duration_seconds):.2f}s ease-in-out infinite alternate;}}
h1{{position:absolute;left:17%;top:34%;margin:0;color:{light};font-size:clamp(28px,5vw,68px);max-width:58%;}}
p{{position:absolute;left:17%;top:49%;margin:0;color:{p1};font-size:clamp(15px,2vw,24px);}}
.cta{{position:absolute;left:17%;top:61%;background:{p0};color:#04100a;font-weight:800;padding:14px 24px;border-radius:18px;}}
@keyframes sweep{{from{{transform:translateX(-45%);}}to{{transform:translateX(45%);}}}}
@keyframes float{{from{{transform:translateY(-3%) scale(.96);}}to{{transform:translateY(7%) scale(1.05);}}}}
</style>
</head>
<body><main class="stage"><section class="glow"></section><div class="beam"></div><div class="orb"></div><h1>{title}</h1><p>Aegis Creative Studio</p><div class="cta">Editable Motion Template</div></main></body>
</html>
"""
        path = job_dir / "animation_storyboard.html"
        path.write_text(html, encoding="utf-8")
        return path

    def _write_photoshop_jsx(self, job_dir: Path, request: MediaCreativeRequest, prompt: str, theme: Theme) -> Path:
        title = safe_title(prompt).replace("\\", "\\\\").replace('"', '\\"')
        p0 = theme.primary
        jsx = f"""#target photoshop
app.documents.add({request.width}, {request.height}, 72, "Aegis Creative Template", NewDocumentMode.RGB, DocumentFill.TRANSPARENT);
var doc = app.activeDocument;
function solidLayer(name, hex) {{
  var layer = doc.artLayers.add();
  layer.name = name;
  var color = new SolidColor();
  color.rgb.hexValue = hex.replace("#", "");
  app.foregroundColor = color;
  doc.selection.select([[0,0],[doc.width,0],[doc.width,doc.height],[0,doc.height]]);
  doc.selection.fill(color);
  doc.selection.deselect();
  return layer;
}}
solidLayer("Background / editable theme base", "#05080d");
var accent = solidLayer("Theme Accent / {p0}", "{p0}");
accent.opacity = 28;
var textLayer = doc.artLayers.add();
textLayer.kind = LayerKind.TEXT;
textLayer.name = "Headline / editable";
textLayer.textItem.contents = "{title}";
textLayer.textItem.position = [doc.width.value * 0.16, doc.height.value * 0.40];
textLayer.textItem.size = Math.max(36, doc.width.value / 24);
var subLayer = doc.artLayers.add();
subLayer.kind = LayerKind.TEXT;
subLayer.name = "Subhead / editable";
subLayer.textItem.contents = "Aegis Creative Studio";
subLayer.textItem.position = [doc.width.value * 0.16, doc.height.value * 0.50];
subLayer.textItem.size = Math.max(18, doc.width.value / 55);
"""
        path = job_dir / "photoshop_template.jsx"
        path.write_text(jsx, encoding="utf-8")
        return path

    def _write_music_assets(self, job_dir: Path, request: MediaCreativeRequest, prompt: str, theme: Theme) -> list[MediaAsset]:
        text = f"{prompt} {request.style}".lower()
        genre = "modern cinematic"
        bpm = 96
        if any(term in text for term in ("lofi", "lo-fi", "chill", "study")):
            genre = "lofi hip hop"
            bpm = 82
        elif any(term in text for term in ("trap", "drill", "808")):
            genre = "dark trap"
            bpm = 142
        elif any(term in text for term in ("house", "edm", "dance", "club")):
            genre = "melodic house"
            bpm = 124
        elif "techno" in text:
            genre = "techno"
            bpm = 132
        elif any(term in text for term in ("boom bap", "hip hop", "rap")):
            genre = "hip hop"
            bpm = 92
        elif any(term in text for term in ("cinematic", "trailer", "epic")):
            genre = "cinematic hybrid"
            bpm = 88

        key = "A minor"
        if any(term in text for term in ("bright", "happy", "uplift", "major")):
            key = "C major"
        elif any(term in text for term in ("dark", "moody", "minor", "cyber")):
            key = "C minor"

        arrangement = {
            "kind": "music_beat",
            "prompt": request.prompt,
            "effective_prompt": prompt,
            "theme": {"primary": theme.primary, "palette": theme.palette},
            "music_profile": {
                "genre": genre,
                "bpm": bpm,
                "key": key,
                "time_signature": "4/4",
                "preview_seconds": max(2.0, min(float(request.duration_seconds), 16.0)),
            },
            "sections": [
                {"name": "Intro", "bars": "1-4", "direction": "Filtered chords, sparse hats, and a clear mood cue."},
                {"name": "Build", "bars": "5-8", "direction": "Bring in kick pattern, bass movement, and ear-candy transitions."},
                {"name": "Drop", "bars": "9-16", "direction": "Full drums, bass, lead motif, and the strongest hook."},
                {"name": "Outro", "bars": "17-20", "direction": "Strip back elements so revisions can extend or loop cleanly."},
            ],
            "drum_pattern": {
                "kick": "Strong hits on beat 1 with syncopated support before beat 3.",
                "snare": "Backbeat on beats 2 and 4.",
                "hat": "Eighth-note pulse with occasional sixteenth-note rolls.",
                "perc": "Short transition fills at section boundaries.",
            },
            "musical_layers": [
                {"name": "Bass", "notes": ["C1", "Eb1", "G1", "Bb1"] if key == "C minor" else ["A1", "C2", "E2", "G2"], "editable": True},
                {"name": "Chords", "notes": ["Cm", "Ab", "Eb", "Bb"] if key == "C minor" else ["Am", "F", "C", "G"], "editable": True},
                {"name": "Lead", "notes": ["root", "minor third", "fifth", "octave"], "editable": True},
                {"name": "FX", "notes": ["reverse sweep", "impact", "short riser"], "editable": True},
            ],
            "mix_notes": [
                "Keep kick and bass separated with a short sidechain envelope.",
                "Leave headroom for voiceover or UI sound effects.",
                "Export stems for drums, bass, music, FX, and master preview.",
            ],
            "revision_strategy": [
                "Change BPM or key without rewriting the entire arrangement.",
                "Swap drum intensity, bass pattern, or lead motif independently.",
                "Use the previous job id to keep theme and arrangement continuity.",
            ],
        }

        sheet = [
            "# Aegis Beat Sheet",
            "",
            f"- Genre: {genre}",
            f"- BPM: {bpm}",
            f"- Key: {key}",
            f"- Theme color: {theme.primary}",
            f"- Prompt: {request.prompt}",
            "",
            "## Arrangement",
            "",
            "Intro: filtered chords and sparse hats.",
            "Build: kick, bass movement, and short transition fills.",
            "Drop: full drums, bass, lead motif, and hook energy.",
            "Outro: stripped-back loopable ending.",
            "",
            "## Revision Notes",
            "",
            "Preserve the musical identity when the user asks for smaller changes. Adjust BPM, key, drum density, lead sound, or mix balance independently before generating a full replacement.",
        ]

        arrangement_path = job_dir / "beat_arrangement.json"
        sheet_path = job_dir / "beat_sheet.md"
        wav_path = job_dir / "beat_preview.wav"
        write_json(arrangement_path, arrangement)
        sheet_path.write_text("\n".join(sheet), encoding="utf-8")
        self._write_wav_preview(wav_path, bpm, key, float(arrangement["music_profile"]["preview_seconds"]))

        return [
            self._asset(sheet_path, request.kind, "md", "beat sheet and revision notes", "text/markdown", True),
            self._asset(arrangement_path, request.kind, "json", "editable beat arrangement", "application/json", True),
            self._asset(wav_path, request.kind, "wav", "local beat preview", "audio/wav", True, arrangement_path.name),
        ]

    def _write_wav_preview(self, path: Path, bpm: int, key: str, duration_seconds: float) -> None:
        sample_rate = 44100
        total_samples = int(sample_rate * max(2.0, min(duration_seconds, 16.0)))
        beats_per_second = bpm / 60.0
        root_name = key.split()[0].upper().replace("M", "")
        root_freqs = {
            "A": 110.0,
            "B": 123.47,
            "C": 130.81,
            "D": 146.83,
            "E": 164.81,
            "F": 174.61,
            "G": 196.0,
        }
        root = root_freqs.get(root_name[:1], 110.0)
        scale = [1.0, 1.2, 1.5, 2.0] if "minor" in key.lower() else [1.0, 1.25, 1.5, 2.0]

        def pulse(position: float, target: float, width: float) -> float:
            delta = abs(position - target)
            delta = min(delta, 4.0 - delta)
            if delta >= width:
                return 0.0
            return (1.0 - delta / width) ** 2

        frames = bytearray()
        for i in range(total_samples):
            t = i / sample_rate
            beat = (t * beats_per_second) % 4.0
            global_beat = t * beats_per_second
            bar = int(global_beat // 4)
            noise = math.sin(i * 12.9898 + 78.233) * 43758.5453
            noise = (noise - math.floor(noise)) * 2.0 - 1.0

            kick_env = pulse(beat, 0.0, 0.12) + pulse(beat, 2.55, 0.08)
            kick_freq = 42.0 + 38.0 * kick_env
            kick = math.sin(2.0 * math.pi * kick_freq * t) * kick_env * 0.52

            snare_env = pulse(beat, 1.0, 0.07) + pulse(beat, 3.0, 0.07)
            snare = noise * snare_env * 0.26

            hat_phase = (global_beat * 2.0) % 1.0
            hat = noise * math.exp(-hat_phase * 18.0) * 0.055

            chord_root = root * scale[bar % len(scale)]
            bass_gate = 0.58 + 0.42 * math.sin(2.0 * math.pi * global_beat)
            bass = math.sin(2.0 * math.pi * (chord_root / 2.0) * t) * bass_gate * 0.16

            lead_step = int(global_beat * 2.0) % len(scale)
            lead_freq = root * 2.0 * scale[lead_step]
            lead_env = 0.5 + 0.5 * math.sin(2.0 * math.pi * global_beat / 8.0)
            lead = math.sin(2.0 * math.pi * lead_freq * t) * lead_env * 0.065

            sample = max(-1.0, min(1.0, kick + snare + hat + bass + lead))
            frames.extend(struct.pack("<h", int(sample * 32767)))

        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(bytes(frames))

    def _write_video_edit_assets(self, job_dir: Path, request: MediaCreativeRequest, prompt: str, theme: Theme) -> list[MediaAsset]:
        duration = max(4.0, min(float(request.duration_seconds), 60.0))
        edit = {
            "kind": "video_edit",
            "prompt": request.prompt,
            "effective_prompt": prompt,
            "theme": {"primary": theme.primary, "palette": theme.palette},
            "duration_seconds": duration,
            "timeline": [
                {"start": 0.0, "end": round(duration * 0.18, 2), "shot": "Hook", "direction": "Open on the strongest visual or problem statement."},
                {"start": round(duration * 0.18, 2), "end": round(duration * 0.42, 2), "shot": "Context", "direction": "Show supporting footage, UI, or subject detail with quick pacing."},
                {"start": round(duration * 0.42, 2), "end": round(duration * 0.74, 2), "shot": "Payoff", "direction": "Reveal the main transformation, feature, or emotional beat."},
                {"start": round(duration * 0.74, 2), "end": duration, "shot": "Close", "direction": "End with clear branding, call to action, or loop-ready final frame."},
            ],
            "transitions": [
                {"at": round(duration * 0.18, 2), "type": "match cut or speed ramp", "note": "Use only if it reinforces the subject motion."},
                {"at": round(duration * 0.42, 2), "type": "soft flash or UI wipe", "note": "Keep contrast readable."},
                {"at": round(duration * 0.74, 2), "type": "accent-color reveal", "note": "Tie the ending to the inferred theme color."},
            ],
            "captions": [
                {"time": 0.0, "text": safe_title(prompt), "style": "large readable hook"},
                {"time": round(duration * 0.45, 2), "text": "Refined by Aegis", "style": "compact support line"},
            ],
            "sound_design": [
                "Short impact on the opening cut.",
                "Subtle risers before major reveals.",
                "Keep music under dialogue or captions.",
            ],
            "export_targets": [
                {"format": "mp4", "codec": "h264", "note": "Primary social/web delivery target."},
                {"format": "webm", "codec": "vp9", "note": "Transparent or web-friendly alternate when supported."},
                {"format": "gif", "codec": "palette", "note": "Short preview loops only."},
            ],
            "revision_strategy": [
                "If feedback asks for pacing changes, adjust timeline timings first.",
                "If feedback asks for style changes, keep edit structure and update theme, transitions, and captions.",
                "If source footage changes, preserve timeline intent and rebuild only source-specific shot notes.",
            ],
        }

        brief = [
            "# Aegis Video Edit Brief",
            "",
            f"- Duration: {duration:.1f}s",
            f"- Theme color: {theme.primary}",
            f"- Prompt: {request.prompt}",
            "",
            "## Edit Direction",
            "",
            "Open fast, establish context, land the strongest payoff, and close with a clean branded or loop-ready frame.",
            "",
            "## Feedback Handling",
            "",
            "Use the edit decision list as the source of truth. For most feedback, revise timing, captions, transitions, sound, or export settings before rebuilding the whole package.",
        ]

        edit_path = job_dir / "edit_decision_list.json"
        brief_path = job_dir / "video_edit_brief.md"
        write_json(edit_path, edit)
        brief_path.write_text("\n".join(brief), encoding="utf-8")

        return [
            self._asset(brief_path, request.kind, "md", "video edit brief", "text/markdown", True),
            self._asset(edit_path, request.kind, "json", "editable edit decision list", "application/json", True),
        ]

    def _plan_for(self, kind: str) -> list[str]:
        plans = {
            "image": ["Infer theme color", "Create editable vector source", "Render PNG preview", "Save provider prompt pack"],
            "video": ["Build storyboard", "Create motion prompt pack", "Render GIF/HTML preview", "Prepare future MP4 adapter slot"],
            "animation": ["Create loopable HTML animation", "Save SVG/vector source", "Render motion preview"],
            "gif": ["Create motion frames", "Render loop preview", "Save editable source package"],
            "video_edit": ["Analyze source intent", "Create edit decision list", "Plan captions, transitions, and sound", "Prepare export notes"],
            "music_beat": ["Infer genre, BPM, and key", "Create drum and melody arrangement", "Render WAV beat preview", "Save stem and revision notes"],
            "psd_template": ["Create layer manifest", "Create Photoshop JSX builder", "Write flattened PSD preview"],
        }
        return plans.get(kind, ["Infer theme", "Create editable source package", "Render preview", "Save revision metadata"])

    def _asset(
        self,
        path: Path,
        kind: str,
        fmt: str,
        role: str,
        mime_type: str,
        editable: bool,
        derived_from: str = "",
    ) -> MediaAsset:
        return MediaAsset(
            path=str(path),
            kind=kind,
            format=fmt,
            role=role,
            mime_type=mime_type,
            editable=editable,
            derived_from=derived_from,
        )
