"""Upload, storage, and Muse Spark metadata for designer media assets."""
from __future__ import annotations

import mimetypes
from typing import Any

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpRequest

from apps.designer_studio.models import DesignerMediaAsset, MediaAssetType, ProposalTemplate
from apps.rfp_debate.meta_client import MetaModelClient

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm", "video/quicktime"}
MAX_ASSET_BYTES = 80 * 1024 * 1024


def _detect_media_type(content_type: str, name: str) -> MediaAssetType | None:
    ct = content_type or mimetypes.guess_type(name)[0] or ""
    if ct in ALLOWED_IMAGE_TYPES or ct.startswith("image/"):
        return MediaAssetType.IMAGE
    if ct in ALLOWED_VIDEO_TYPES or ct.startswith("video/"):
        return MediaAssetType.VIDEO
    return None


def _image_dimensions(upload: UploadedFile) -> tuple[int | None, int | None]:
    try:
        from PIL import Image

        upload.seek(0)
        with Image.open(upload) as img:
            return img.size
    except Exception:
        return None, None
    finally:
        upload.seek(0)


def save_designer_asset(
    *,
    designer,
    upload: UploadedFile,
    request: HttpRequest,
    template: ProposalTemplate | None = None,
    venue_map=None,
) -> DesignerMediaAsset:
    if upload.size > MAX_ASSET_BYTES:
        raise ValueError(f"File exceeds {MAX_ASSET_BYTES // (1024 * 1024)}MB limit.")

    content_type = upload.content_type or mimetypes.guess_type(upload.name)[0] or ""
    media_type = _detect_media_type(content_type, upload.name)
    if media_type is None:
        raise ValueError("Only image and video files are supported.")

    width, height = (None, None)
    if media_type == MediaAssetType.IMAGE:
        width, height = _image_dimensions(upload)

    asset = DesignerMediaAsset.objects.create(
        designer=designer,
        template=template,
        venue_map=venue_map,
        file=upload,
        original_name=upload.name,
        content_type=content_type,
        file_size=upload.size,
        media_type=media_type,
        width=width,
        height=height,
        metadata_json={"upload_status": "stored"},
    )
    enrich_asset_metadata(asset, request)
    return asset


def asset_public_url(asset: DesignerMediaAsset, request: HttpRequest) -> str:
    return request.build_absolute_uri(asset.file.url)


def enrich_asset_metadata(asset: DesignerMediaAsset, request: HttpRequest) -> DesignerMediaAsset:
    url = asset_public_url(asset, request)
    base_meta = {
        "id": str(asset.id),
        "url": url,
        "media_type": asset.media_type,
        "original_name": asset.original_name,
        "content_type": asset.content_type,
        "file_size": asset.file_size,
        "width": asset.width,
        "height": asset.height,
    }
    client = MetaModelClient()
    prompt = (
        "You analyze media for a hospitality proposal template designer. "
        "Return JSON: description (string), suggested_placement (hero|gallery|sidebar|background), "
        "dominant_mood (string), embed_hint (how to use in HTML img/video tags with the given url)."
    )
    user = (
        f"Media metadata:\n{base_meta}\n"
        "If information is limited, infer reasonable creative usage for a luxury hotel RFP proposal."
    )
    raw = client.complete_json(
        model_id=settings.META_MODEL_SPARK,
        system_prompt=prompt,
        user_content=user,
        fixture_kind="designer_asset_meta",
    )
    asset.metadata_json = {**base_meta, **raw, "upload_status": "ready"}
    asset.save(update_fields=["metadata_json"])
    return asset


def format_assets_for_agent(assets: list[DesignerMediaAsset]) -> str:
    if not assets:
        return ""
    lines = ["Attached media assets (already stored — embed using absolute URLs):"]
    for asset in assets:
        meta = asset.metadata_json or {}
        lines.append(
            f"- {meta.get('original_name', asset.original_name)} [{asset.media_type}] "
            f"url={meta.get('url')} "
            f"description={meta.get('description', 'n/a')} "
            f"placement={meta.get('suggested_placement', 'gallery')} "
            f"embed_hint={meta.get('embed_hint', 'Use <img> or <video controls>')}"
        )
    return "\n".join(lines)


def assets_metadata_block(assets: list[DesignerMediaAsset]) -> list[dict[str, Any]]:
    return [a.metadata_json or {} for a in assets]
