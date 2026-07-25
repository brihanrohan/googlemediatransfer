# Google Photos Downloader

This script downloads images from a shared Google Drive folder named "Google Photos" (and its subfolders) into a single local folder. Files that collide with an existing name are placed in a `duplicates` subfolder.

## What it does

- Connects to Google Drive using OAuth 2.0
- Finds a folder named `Google Photos`
- Recursively walks all subfolders
- Downloads supported image files
- Saves everything into one output directory
- Sends duplicates into `duplicates/`

## Requirements

- Python 3.8+
- A Google Cloud project
- OAuth client credentials for a desktop app

## Google Cloud setup

1. Go to the Google Cloud Console: https://console.cloud.google.com/
2. Create or select a project.
3. Enable the Google Drive API:
   - Go to APIs & Services -> Library
   - Search for "Google Drive API"
   - Click Enable
4. Create OAuth credentials:
   - Go to APIs & Services -> Credentials
   - Click Create Credentials -> OAuth client ID
   - Choose "Desktop app"
   - Click Create
5. Download the JSON file and save it as `credentials.json` in this project folder.
6. Run the script. The first time it will open a browser window and ask you to sign in.
   - After successful sign-in, Google will create `token.json` for future runs.

## Run the script

```bash
cd /home/brian/googlemediatransfer
. .venv/bin/activate
python googledrivedownload.py
```

## Output folder

By default, files are downloaded into:

```bash
./downloaded_google_photos
```

## Notes

- The script only downloads common image extensions such as `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`, `.tif`, `.tiff`, `.heic`, and `.heif`.
- If you run the script again, it will check the MD5 hash of each image already present in the output folder and skip downloading files that match, so it does not re-download everything.
- If you want to change the folder name or output directory, use:

```bash
python googledrivedownload.py --folder-name "Google Photos" --output-dir ./downloaded_google_photos
```
