# Odexpo Gallery Scraper

A simple web scraper for extracting images and metadata from the Fabienne Vincent gallery website (fabienne-vincent.odexpo.com).

## Features

- ✅ Domain-restricted crawling (only fabienne-vincent.odexpo.com)
- ✅ Image extraction with metadata (alt text, title, description)
- ✅ Automatic image downloading with organized folder structure
- ✅ Basic request throttling and error handling
- ✅ JSON metadata export
- ✅ Progress tracking and summary reporting

## Configuration

The crawler is configured to only access `fabienne-vincent.odexpo.com` as specified in `config.py`:

- **Allowed Domain**: `fabienne-vincent.odexpo.com`
- **Max Concurrent Requests**: 3
- **Request Delay**: 1.0 seconds
- **Timeout**: 30 seconds

## Usage

### Basic Usage

```bash
# Install dependencies (if using uv)
uv sync

# Run the scraper
python main.py
```

### What it does

1. Starts crawling from `https://fabienne-vincent.odexpo.com`
2. Extracts all images from each page
3. Downloads images to `assets/images/` with organized folder structure
4. Saves metadata to `assets/metadata.json`
5. Follows internal links to discover more gallery pages
6. Provides a summary of downloaded content

### Output Structure

```
assets/
├── images/           # Downloaded images organized by URL path
│   ├── gallery1/
│   ├── gallery2/
│   └── ...
└── metadata.json     # Complete metadata for all images
```

### Metadata Format

Each image entry in `metadata.json` includes:

```json
{
  "original_url": "https://fabienne-vincent.odexpo.com/path/to/image.jpg",
  "local_path": "assets/images/path/to/image.jpg",
  "filename": "image.jpg",
  "size_bytes": 123456,
  "alt_text": "Image description",
  "title": "Image title",
  "description": "Extended description",
  "score": 8.5,
  "source_page": "https://fabienne-vincent.odexpo.com/gallery",
  "page_title": "Gallery Page Title",
  "found_at": 1234567890.123
}
```

## Customization

Edit `config.py` to modify:

- Domain restrictions
- Request throttling settings
- File paths
- Image size limits
- Supported image formats

## Notes

- The crawler respects robots.txt and implements basic throttling
- Only downloads images from the allowed domain
- Automatically handles relative and absolute URLs
- Creates directory structure reflecting the website organization
- Includes comprehensive error handling and logging
