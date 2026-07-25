import argparse
import hashlib
import io
import os
import re
from pathlib import Path
from typing import List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload



SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".webp",
    ".tif",
    ".tiff",
    ".heic",
    ".heif",
}


def escape_query_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def get_credentials(token_path: Path, client_secret_path: Path):
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not client_secret_path.exists():
                raise FileNotFoundError(
                    "credentials.json was not found. Create a Google Cloud OAuth client and save it as "
                    f"{client_secret_path}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
            creds = flow.run_local_server(port=0)

        token_path.write_text(creds.to_json(), encoding="utf-8")

    return creds


def get_drive_service(token_path: Path, client_secret_path: Path):
    creds = get_credentials(token_path, client_secret_path)
    return build("drive", "v3", credentials=creds)


def list_drive_items(service, query: str, fields: str = "files(id, name, mimeType, md5Checksum)", page_size: int = 1000):
    items = []
    page_token = None

    while True:
        request = (
            service.files()
            .list(
                q=query,
                pageSize=page_size,
                fields=fields,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageToken=page_token,
            )
        )
        response = request.execute()
        items.extend(response.get("files", []))

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return items


def find_folder(service, folder_name: str):
    escaped_name = escape_query_value(folder_name)
    queries = [
        f"name = '{escaped_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        f"sharedWithMe = true and name = '{escaped_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
    ]

    for query in queries:
        items = list_drive_items(service, query, fields="files(id, name)", page_size=100)
        if items:
            return items[0]["id"]

    raise FileNotFoundError(f"Could not find a folder named '{folder_name}' that you can access.")


def is_image_file(name: str) -> bool:
    return Path(name).suffix.lower() in IMAGE_EXTENSIONS


def build_existing_hash_index(output_dir: Path) -> dict:
    hash_index = {}
    if not output_dir.exists():
        return hash_index

    for path in output_dir.rglob("*"):
        if not path.is_file():
            continue

        try:
            digest = hashlib.md5(path.read_bytes()).hexdigest()
        except OSError:
            continue

        if digest not in hash_index:
            hash_index[digest] = path

    return hash_index


def find_matching_local_file(existing_hash_index: dict, md5_checksum: Optional[str]) -> Optional[Path]:
    if not md5_checksum:
        return None
    return existing_hash_index.get(md5_checksum)


def sanitize_name(name: str) -> str:
    invalid_chars = '<>:"/\\|?*\x00-\x1f'
    for char in invalid_chars:
        name = name.replace(char, "_")
    return name


def ensure_unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def build_destination_path(output_dir: Path, item_name: str, relative_parts: List[str]) -> Path:
    safe_parts = [sanitize_name(part) for part in relative_parts + [Path(item_name).stem] if sanitize_name(part)]
    safe_name = "__".join(safe_parts) or sanitize_name(Path(item_name).stem)
    suffix = Path(item_name).suffix
    primary_path = output_dir / f"{safe_name}{suffix}"

    if not primary_path.exists():
        return primary_path

    duplicates_dir = output_dir / "duplicates"
    duplicates_dir.mkdir(parents=True, exist_ok=True)
    return ensure_unique_path(duplicates_dir / f"{safe_name}{suffix}")


def download_file(service, file_id: str, destination: Path):
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        if status:
            pass

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(fh.getvalue())


def download_folder_tree(
    service,
    folder_id: str,
    output_dir: Path,
    relative_parts: Optional[List[str]] = None,
    existing_hash_index: Optional[dict] = None,
):
    if relative_parts is None:
        relative_parts = []
    if existing_hash_index is None:
        existing_hash_index = {}

    query = f"'{folder_id}' in parents and trashed = false"
    items = list_drive_items(service, query)
    for item in items:
        item_name = item["name"]
        if item.get("mimeType") == "application/vnd.google-apps.folder":
            next_parts = relative_parts + [item_name]
            download_folder_tree(service, item["id"], output_dir, next_parts, existing_hash_index)
        elif is_image_file(item_name):
            md5_checksum = item.get("md5Checksum")
            matching_path = find_matching_local_file(existing_hash_index, md5_checksum)
            if matching_path:
                print(f"Skipped existing: {matching_path}")
                continue

            destination = build_destination_path(output_dir, item_name, relative_parts)
            download_file(service, item["id"], destination)
            if md5_checksum:
                existing_hash_index[md5_checksum] = destination
            print(f"Downloaded: {destination}")


def main():
    parser = argparse.ArgumentParser(description="Download images from a shared Google Drive folder tree")
    parser.add_argument("--folder-name", default="Google Photos", help="Folder name to search for")
    parser.add_argument(
        "--output-dir",
        default="./downloaded_google_photos",
        help="Local directory where files will be saved",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    token_path = script_dir / "token.json"
    client_secret_path = script_dir / "credentials.json"

    print("Connecting to Google Drive...")
    service = get_drive_service(token_path, client_secret_path)

    folder_id = find_folder(service, args.folder_name)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading images from folder '{args.folder_name}' into {output_dir}")
    existing_hash_index = build_existing_hash_index(output_dir)
    download_folder_tree(service, folder_id, output_dir, existing_hash_index=existing_hash_index)
    print("Finished.")


if __name__ == "__main__":
    main()
