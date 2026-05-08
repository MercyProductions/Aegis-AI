from __future__ import annotations

from collections.abc import Iterable


EXPLANATION_PREFIXES: tuple[str, ...] = (
    "how do i",
    "how can i",
    "how should i",
    "what command",
    "what is the command",
    "explain",
    "tell me how",
    "show me how",
)

EXECUTION_VALIDATION_PHRASES: tuple[str, ...] = (
    "and build it",
    "also build it",
    "then build it",
    "build and run",
    "build/run",
    "build it",
    "build this",
    "build the project",
    "build the app",
    "launch it",
    "launch this",
    "launch the app",
    "launch the project",
    "start it",
    "start this",
    "start the app",
    "start the project",
    "execute it",
    "execute this",
    "execute the app",
    "execute the project",
    "run build",
    "run the build",
    "run it",
    "run this",
    "run the app",
    "run the project",
    "run validation",
    "validate it",
    "validate this",
    "validate the project",
    "verify it",
    "verify this",
    "verify build",
    "verify the build",
    "verify the project",
    "check the build",
    "check for errors",
    "run tests",
    "run the tests",
    "test it",
    "test this",
    "compile it",
    "compile this",
    "compile the app",
    "compile the project",
    "make sure it builds",
    "make sure it compiles",
    "make sure this compiles",
    "make sure there are no errors",
    "no build errors",
    "no compilation errors",
    "no syntax errors",
    "fix any errors",
    "fix build errors",
    "repair the build",
    "repair build",
    "continue build",
    "continue the build",
    "continue validation",
    "last failed build",
    "failed build",
    "build failed",
    "rerun build",
    "rerun the build",
    "rerun validation",
    "rerun the validation",
    "try the build again",
    "try building again",
    "run it again",
    "you didn't build",
    "you didnt build",
    "didn't build",
    "didnt build",
)

CREATIVE_MEDIA_ACTION_TERMS: tuple[str, ...] = (
    "generate",
    "create",
    "make",
    "design",
    "draw",
    "render",
    "produce",
    "draft",
    "mock up",
    "mockup",
)

CREATIVE_MEDIA_TERMS: tuple[str, ...] = (
    "text to image",
    "text-to-image",
    "image to image",
    "image-to-image",
    "image",
    "picture",
    "photo",
    "illustration",
    "logo",
    "icon",
    "ui mockup",
    "mockup",
    "product mockup",
    "thumbnail",
    "banner",
    "poster",
    "wallpaper",
    "avatar",
    "sticker",
    "brand kit",
    "style transfer",
    "background removal",
    "upscale",
    "variation",
    "video",
    "promo video",
    "logo intro",
    "social clip",
    "storyboard",
    "animation",
    "gif",
    "music",
    "beat",
    "drum loop",
    "melody",
    "song",
    "loop",
    "voice",
    "voiceover",
    "narration",
    "text to speech",
    "text-to-speech",
    "tts",
    "sound effect",
    "audio",
)

CREATIVE_MEDIA_CODE_CONTEXT_TERMS: tuple[str, ...] = (
    "component",
    "react component",
    "vue component",
    "code",
    "function",
    "api",
    "script",
    "module",
    "upload",
    "image processing",
    "computer vision code",
    "svg component",
    "css",
    "typescript",
    "javascript",
)


def normalize_prompt_text(message: str) -> str:
    normalized_chars: list[str] = []
    for char in (message or "").strip().lower():
        if char.isalnum() or char in {"'", "+", "#"}:
            normalized_chars.append(char)
        else:
            normalized_chars.append(" ")
    return f" {' '.join(''.join(normalized_chars).split())} "


def prompt_has_explanation_prefix(message: str) -> bool:
    normalized = normalize_prompt_text(message)
    if not normalized.strip():
        return False
    return any(_contains_phrase(normalized, prefix) for prefix in EXPLANATION_PREFIXES)


def prompt_contains_any_phrase(message: str, phrases: Iterable[str]) -> bool:
    normalized = normalize_prompt_text(message)
    if not normalized.strip():
        return False
    return any(_contains_phrase(normalized, phrase) for phrase in phrases)


def prompt_requests_execution_validation(message: str, *, extra_phrases: Iterable[str] = ()) -> bool:
    normalized = normalize_prompt_text(message)
    if not normalized.strip():
        return False
    if prompt_has_explanation_prefix(normalized):
        return False
    return any(
        _contains_phrase(normalized, phrase)
        for phrase in (*EXECUTION_VALIDATION_PHRASES, *tuple(extra_phrases))
    )


def prompt_requests_creative_media(message: str) -> bool:
    normalized = normalize_prompt_text(message)
    if not normalized.strip():
        return False
    if not any(_contains_phrase(normalized, term) for term in CREATIVE_MEDIA_ACTION_TERMS):
        return False
    if not any(_contains_phrase(normalized, term) for term in CREATIVE_MEDIA_TERMS):
        return False

    # Code-context prompts like "create an image upload component" should stay on
    # the coding route unless they also name a clear generated-media artifact.
    artifact_kind = infer_creative_media_kind(normalized)
    if artifact_kind in {"image", "image_to_image"} and any(
        _contains_phrase(normalized, term) for term in CREATIVE_MEDIA_CODE_CONTEXT_TERMS
    ):
        return False
    return True


def infer_creative_media_kind(message: str) -> str | None:
    normalized = normalize_prompt_text(message)
    if not normalized.strip():
        return None

    kind_patterns: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("logo_intro", ("logo intro", "animated logo intro")),
        ("promo_video", ("promo video", "app showcase video", "showcase video")),
        ("social_clip", ("social clip", "social media clip")),
        ("storyboard_video", ("storyboard video", "storyboard to video", "storyboard")),
        ("video", ("text to video", "text-to-video", "image to video", "image-to-video", "video")),
        ("animation", ("animation", "animated", "gif")),
        ("music_beat", ("beat", "drum loop", "melody", "music", "song", "loop generation")),
        ("voiceover", ("voiceover", "narration", "text to speech", "text-to-speech", "tts")),
        ("sound_effect", ("sound effect", "sound effects")),
        ("brand_kit", ("brand kit", "brand identity")),
        ("ui_mockup", ("ui mockup", "interface mockup", "app mockup", "screen mockup")),
        ("product_mockup", ("product mockup", "device mockup")),
        ("background_removal", ("background removal", "remove background")),
        ("style_transfer", ("style transfer",)),
        ("upscale", ("upscale", "upscaling")),
        ("variation", ("variation", "variations")),
        ("thumbnail", ("thumbnail",)),
        ("icon", ("icon", "icons")),
        ("logo", ("logo", "logomark", "brand mark")),
        ("image", ("text to image", "text-to-image", "image", "picture", "photo", "illustration", "poster", "banner", "wallpaper", "avatar", "sticker")),
    )
    for kind, patterns in kind_patterns:
        if any(_contains_phrase(normalized, pattern) for pattern in patterns):
            return kind
    return None


def creative_media_studio_for_kind(kind: str | None) -> str:
    normalized = (kind or "image").strip().lower()
    if normalized in {"video", "text_to_video", "image_to_video", "promo_video", "logo_intro", "app_showcase", "social_clip", "storyboard_video", "animation", "gif", "video_edit"}:
        return "video"
    if normalized in {"music_beat", "music", "drum_loop", "melody", "loop", "arrangement"}:
        return "beat"
    if normalized in {"voice", "voiceover", "narration", "sound_effect", "audio_cleanup"}:
        return "voice"
    return "image"


def _contains_phrase(normalized: str, phrase: str) -> bool:
    clean = normalize_prompt_text(phrase).strip()
    if not clean:
        return False
    return f" {clean} " in normalized
