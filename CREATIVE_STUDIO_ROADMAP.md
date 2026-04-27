# Aegis Creative Studio Roadmap

This is the expansion plan for turning Aegis ChatBot into a full creative generation workspace, not just a text assistant with an image button.

## Core Principle

Creative work should be iterative. Every generated image, video, GIF, animation, or Photoshop template needs a persistent job folder with source prompts, theme decisions, manifests, editable layers, previews, and revision history. When the user says "make it cleaner", "more cinematic", or "use blue instead", Aegis should revise the existing job instead of starting from scratch unless the user asks for a fresh direction.

## First Slice Implemented

- Backend media capability endpoint: `GET /api/media/capabilities`
- Backend creative job endpoint: `POST /api/media/jobs`
- Persistent job folders under `Website/ChatBot/workspace/creative_media`
- Theme color inference when the user does not specify one
- Prompt packs for image, video, animation, and PSD workflows
- Editable SVG template output
- Editable layer manifest output
- Photoshop JSX builder output
- Flattened PSD preview support when Pillow is installed
- GIF and PNG preview support when Pillow is installed
- HTML animation/storyboard output for animation and video packages
- Desktop Creative Studio card with image, video, GIF/animation, PSD template, and revise-last actions

## Must-Have Creative Capabilities

1. Image generation
- Text-to-image
- Image-to-image
- Inpainting/outpainting
- Background removal
- Upscale and face/detail restore
- Brand-safe template generation
- Multi-size exports for social, web, ads, thumbnails, banners, and app assets

2. Video generation
- Text-to-video
- Image-to-video
- Storyboard first, render second
- Shot lists, camera movement, duration, fps, and aspect ratio controls
- Consistent character/product/style preservation
- MP4/WebM export through a renderer such as ffmpeg

3. Animation generation
- HTML/CSS motion templates
- SVG animation
- Lottie JSON export
- Sprite sheet export
- Transparent-background animation options
- UI micro-interactions for buttons, loading states, and app intros

4. GIF generation
- Looping GIFs
- Reaction/sticker GIFs
- Product demo loops
- Before/after comparison GIFs
- Optimized file-size presets
- Frame-by-frame preview and edit notes

5. Photoshop template generation
- PSD preview
- Photoshop JSX script that rebuilds editable layers
- Layer manifests with named groups
- Smart-object placeholder strategy
- Safe margins and export slices
- Font, palette, and brand-token metadata

6. Iteration memory
- Every job stores `previous_job_id`
- Feedback becomes a revision instruction
- Preserve useful composition and palette unless feedback says otherwise
- Compare previous vs revised prompt pack
- Record user preferences such as "always use darker green" or "more cinematic"

## Theme Behavior

If the user gives a color, use it. If not, infer one from the prompt:

- Aegis, finance, security, growth: green
- Luxury, premium, royal, wealth: gold
- Cyber, gaming, futuristic: purple
- SaaS, corporate, productivity: blue
- Sports, speed, energy: orange
- Beauty, fashion, romantic: pink
- Alert, urgency, sale: red

The theme should produce a full palette, not just a single color.

## Provider Expansion

The backend should support provider adapters behind one creative gateway:

- Local template renderer for SVG, PNG, GIF, HTML, JSX, and PSD package files
- Cloud image providers for photoreal generation
- Cloud video providers for image-to-video and text-to-video
- Vector/icon providers for brand kits and app assets
- Lottie/bodymovin pipeline for lightweight UI animation
- ffmpeg renderer for MP4/WebM output

## Additional Ideas

- Brand kit creator: logo marks, colors, typography, export tokens
- Thumbnail generator: YouTube, TikTok, Instagram, X, app store
- Ad creative generator: multiple variants with headline testing
- Product mockup creator: desktop, phone, tablet, billboard, packaging
- Character/style bible: preserve a person, mascot, product, or brand look across jobs
- Creative review mode: Aegis critiques composition, contrast, text fit, and brand consistency
- Batch variants: generate 4-12 directions from one brief
- Asset library: reusable backgrounds, palettes, logos, masks, and overlays
- Prompt remix: keep subject but vary lighting, mood, camera, color, layout
- Export packs: `web`, `social`, `presentation`, `app`, `print`, `photoshop`
- Transparent asset mode for stickers, icons, overlays, and stream alerts
- Before/after revision history with selectable branches

## Next Engineering Tickets

1. Add provider registry for creative models and renderers.
2. Add media job list/detail endpoints.
3. Add desktop job browser with preview thumbnails.
4. Add direct feedback UI tied to `previous_job_id`.
5. Add ffmpeg-based MP4/WebM rendering.
6. Add real layered PSD export or packaged Photoshop automation.
7. Add Lottie JSON export for app and web animation.
8. Add image upload/reference support.
9. Add per-user creative memory and brand presets.
10. Add automated visual QA checks for text overflow, contrast, aspect ratio, and safe margins.
