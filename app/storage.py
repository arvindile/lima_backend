import os
import uuid

# Avatar storage abstraction.
#
# Local disk (the original approach) does NOT survive a Render redeploy on
# the free tier — the filesystem is ephemeral, so every profile picture
# gets wiped the next time you push code. Cloudinary's free tier persists
# forever and needs no credit card, so it's used here whenever credentials
# are present via env vars (CLOUDINARY_CLOUD_NAME / CLOUDINARY_API_KEY /
# CLOUDINARY_API_SECRET on Render).
#
# Locally, if you haven't set up a Cloudinary account, this falls back to
# the old local-disk behavior automatically — no extra setup needed to keep
# developing on your machine.

UPLOAD_DIR = "uploads"
_EXTENSION_BY_CONTENT_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

_cloudinary_configured = False


def _cloudinary_ready() -> bool:
    """Configures the Cloudinary SDK once (lazily) if credentials are set.

    Returns True if Cloudinary is available and configured, False if the
    caller should fall back to local disk storage.
    """
    global _cloudinary_configured
    if _cloudinary_configured:
        return True

    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
    if not (cloud_name and api_key and api_secret):
        return False

    import cloudinary

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )
    _cloudinary_configured = True
    return True


def save_avatar(player_id: str, contents: bytes, content_type: str) -> str:
    """Stores an avatar image and returns the URL to save on the player row.

    Uses Cloudinary when configured (persists across redeploys). Falls back
    to local disk otherwise (original behavior, fine for local dev).
    """
    if _cloudinary_ready():
        import cloudinary.uploader

        # Cloudinary accounts created since mid-2024 use "Dynamic Folder
        # Mode," where slashes inside public_id are just literal characters
        # in the ID — they no longer place the file into a matching folder.
        # asset_folder is the parameter that actually controls where it's
        # organized in the Media Library. public_id stays as just the
        # player's own id (no slashes needed), so re-uploading a new avatar
        # overwrites the same asset instead of piling up orphaned images.
        result = cloudinary.uploader.upload(
            contents,
            public_id=player_id,
            asset_folder="lima/avatars",
            overwrite=True,
            resource_type="image",
        )
        return result["secure_url"]

    extension = _EXTENSION_BY_CONTENT_TYPE[content_type]
    filename = f"{uuid.uuid4()}{extension}"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(contents)
    return f"/uploads/{filename}"