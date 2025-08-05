# Odexpo Gallery Scraper

A web scraper for downloading high-resolution artwork images from the Fabienne Vincent gallery website using Playwright.

## Features

- 🎨 **Gallery Crawling** - Automatically discovers and downloads from all gallery categories
- 🖼️ **High-Resolution Images** - Gets full-size images from lightbox popups
- 📁 **Smart Organization** - Organizes images into category folders
- 🏷️ **Auto-Renaming** - Renames files using artwork titles for better organization
- 📊 **Metadata Collection** - Saves detailed information about each artwork
- 🔄 **Duplicate Prevention** - Avoids re-downloading existing images

## Quick Start

Run the complete workflow automatically - crawl, download, rename, and organize:

```bash
python gallery_tool.py
```

This will:
1. Crawl the gallery and download images
2. Automatically rename files using artwork titles
3. Organize into cleaned category folders
4. Save metadata for all images

## Requirements

- Python 3.11+
- Install dependencies: `pip install -r requirements.txt`

## How It Works

1. **Discovers Categories** - Finds all gallery categories automatically
2. **Crawls Systematically** - Downloads from each category completely before moving to the next
3. **High-Quality Images** - Clicks each image to get full-resolution versions
4. **Smart Naming** - Renames files like `tigre_du_bengale_419.jpg` instead of `739467410189419.jpg`
5. **Organized Storage** - Creates folders like `fauves/`, `animaux-d-afrique/`, etc.

## Output Structure

```
assets/
└── crawl_runs/
    └── 20241208_143022/          # Timestamped run
        ├── images/               # Downloaded images
        │   ├── fauves/          # Category folders
        │   ├── animaux-d-afrique/
        │   └── ...
        └── metadata.json        # Image details and metadata
```

## Configuration

Edit `config.py` to change:
- Target website URL
- Download delays and timeouts
- File organization preferences

## Notes

- Each crawl session creates a timestamped folder
- Respects the website with proper delays between requests
- Handles pagination automatically within each category
- Skips duplicate downloads across multiple runs
