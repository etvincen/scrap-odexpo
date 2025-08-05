# Odexpo Gallery Scraper

A comprehensive web scraper for extracting images and metadata from the Fabienne Vincent gallery website (fabienne-vincent.odexpo.com) with advanced BFS crawling, file organization, and renaming capabilities.

## Features

### 🚀 Advanced Crawler (Recommended)
- ✅ **BFS (Breadth-First Search) Crawling** - Systematically crawls all pages within each category before moving to the next
- ✅ **Select Tag Extraction** - Automatically discovers gallery categories from dropdown selects
- ✅ **Timestamped Crawl Runs** - Each crawl session creates a unique timestamped folder
- ✅ **Category-Aware Pagination** - Follows pagination links within the same gallery category
- ✅ **Thorough Page Processing** - Ensures all images are downloaded before moving to next page
- ✅ **Smart Duplicate Detection** - Prevents re-downloading across multiple runs

### 🏷️ File Management & Organization
- ✅ **Smart File Renaming** - Renames files using artwork titles + last 3 digits for uniqueness
- ✅ **Category Cleaning** - Automatically cleans categories (lowercase, no accents, no underscores)  
- ✅ **Automatic Reorganization** - Sorts existing images into category-based folders
- ✅ **Metadata Synchronization** - Keeps JSON metadata in sync with file changes
- ✅ **Collection Statistics** - View comprehensive statistics about your image collection

### 📝 Basic Crawler
- ✅ Domain-restricted crawling (only fabienne-vincent.odexpo.com)
- ✅ Image extraction with metadata (alt text, title, description)
- ✅ Automatic image downloading with organized folder structure
- ✅ Basic request throttling and error handling
- ✅ JSON metadata export
- ✅ Progress tracking and summary reporting

## Configuration

The crawler is configured in `config.py`:

- **Allowed Domain**: `fabienne-vincent.odexpo.com`
- **Max Concurrent Requests**: 3
- **Request Delay**: 0.5 seconds
- **Timeout**: 30 seconds
- **Gallery Select Class**: `form-control-comb classicomb`

## Usage

### ⚡ Quick Start

The simplest way to get started:

```bash
# Make launcher executable (one time only)
chmod +x gallery_tool.py

# Launch the gallery tool
./gallery_tool.py
```

This automatically detects whether you have `uv` installed and launches the unified interface with all features.

### 🎯 Unified Interface (Recommended)

The unified interface provides all functionality in one convenient menu:

```bash
# Install dependencies (if using uv)
uv sync

# Run the unified interface
uv run python main_unified.py
```

**Available Operations:**
1. **🕷️ Advanced Crawling** - Download new images from gallery
2. **📁 Reorganize Images** - Sort existing images by categories  
3. **🏷️ Rename Files** - Update filenames using titles + clean categories
4. **📊 Show Statistics** - Display collection overview
5. **❌ Exit**

### Individual Scripts

You can also run individual components:

#### Advanced Crawler

```bash
# Run the advanced scraper with BFS and timestamped runs
uv run python main_advanced.py
```

#### File Renaming

```bash
# Rename files using artwork titles + last 3 digits
uv run python rename_files.py
```

#### Image Reorganization

```bash
# Reorganize existing images by categories
uv run python reorganize.py
```

#### Basic Crawler

```bash
# Run the basic scraper
uv run python main.py
```

**What the Advanced Crawler Does:**

1. **Category Discovery**: Extracts gallery categories from select dropdown
2. **BFS Strategy**: Crawls all pages in "FAUVES" category completely before moving to "ANIMAUX" category
3. **Pagination Handling**: Follows "page 1, 2, 3..." links within each category
4. **Timestamped Runs**: Creates `assets/crawl_runs/YYYYMMDD_HHMMSS/` directory
5. **Complete Coverage**: Ensures 16+16+6 images from 3 pages of "FAUVES" before moving on

### Basic Crawler

```bash
# Run the basic scraper
python main.py
```

### Utility Scripts

```bash
# Reorganize existing images by categories
python reorganize.py
```

## File Renaming Feature

The file renaming tool transforms your collection with meaningful filenames:

### Before Renaming:
```
739467410189419.jpg          (cryptic number)
57903569135428.jpg           (cryptic number)
```

### After Renaming:
```
tigre_du_bengale_419.jpg     (title + last 3 digits)
sentinelle_de_la_savane_428.jpg (title + last 3 digits)
```

### Category Cleaning:
```
FAUVES → fauves
ANIMAUX  D_AFRIQUE → animaux-d-afrique
```

**Features:**
- 🏷️ Uses artwork titles from metadata for meaningful names
- 🔢 Keeps last 3 digits from original filename for uniqueness
- 🧹 Cleans categories (lowercase, removes accents and underscores)
- 📁 Moves files to cleaned category folders
- 💾 Updates all metadata files automatically
- 🔍 Dry run mode to preview changes before applying
- ⚠️ Handles filename conflicts automatically

## Advanced Crawler Output Structure

```
assets/
├── crawl_runs/
│   ├── 20241208_143022/          # Timestamped run folder
│   │   ├── images/               # Images organized by category
│   │   │   ├── fauves/          # Cleaned gallery category
│   │   │   │   ├── tigre_du_bengale_419.jpg
│   │   │   │   ├── guepard_en_marche_699.jpg
│   │   │   │   └── ...
│   │   │   ├── animaux-d-afrique/
│   │   │   │   ├── sentinelle_de_la_savane_428.jpg
│   │   │   │   ├── zebre_des_plaines_020.jpg
│   │   │   │   └── ...
│   │   │   └── ...
│   │   └── metadata.json        # Complete metadata with cleaned info
│   └── 20241208_151530/          # Another run
└── images/                       # Legacy basic crawler images
```

## Tool Comparison

| Feature | Basic Crawler | Advanced Crawler | Unified Interface |
|---------|---------------|------------------|-------------------|
| Category Discovery | ❌ Manual | ✅ Automatic (select tags) | ✅ Automatic |
| Crawling Strategy | Random | ✅ BFS (category-aware) | ✅ BFS |
| Pagination | Basic link following | ✅ Smart category pagination | ✅ Smart pagination |
| Run Management | Single folder | ✅ Timestamped runs | ✅ Timestamped runs |
| File Renaming | ❌ None | ❌ None | ✅ Title-based |
| Category Cleaning | ❌ None | ❌ None | ✅ Automatic |
| Collection Management | ❌ None | ❌ None | ✅ Full suite |
| Interactive Interface | ❌ None | ❌ None | ✅ Menu-driven |

## Gallery Crawling Strategy

The advanced crawler implements a sophisticated BFS strategy:

1. **Phase 1**: Extract all gallery categories from select dropdown
2. **Phase 2**: For each category (e.g., "FAUVES"):
   - Crawl page 1 completely (all 16 images)
   - Crawl page 2 completely (all 16 images)  
   - Crawl page 3 completely (all 6 images)
   - Only then move to next category
3. **Phase 3**: Move to next category ("ANIMAUX D'AFRIQUE") and repeat

This ensures complete coverage without missing images due to premature page switching.

## Metadata Format

Each image entry includes:

```json
{
  "original_url": "https://fabienne-vincent.odexpo.com/images/54826/pt_fauves_001.jpg",
  "local_path": "assets/crawl_runs/20241208_143022/images/fauves/pt_fauves_001.jpg",
  "filename": "pt_fauves_001.jpg",
  "size_bytes": 123456,
  "alt_text": "Image description",
  "title": "Image title",
  "description": "FAUVES gallery description",
  "category": "fauves",
  "cleaned_description": "fauves",
  "score": 8.5,
  "source_page": "https://fabienne-vincent.odexpo.com/default.asp?galerie=54826",
  "page_title": "FAUVES - fabienne-vincent",
  "crawl_run": "assets/crawl_runs/20241208_143022",
  "found_at": 1733652622.123
}
```

## Troubleshooting

### "Only getting 1 image per page"
✅ **Fixed in Advanced Crawler**: Uses `scan_full_page=True` and `scroll_delay=1.0` to ensure all images load

### "Missing pagination within categories"
✅ **Fixed in Advanced Crawler**: Smart pagination detection keeps crawling within the same gallery category

### "Duplicate downloads across runs"
✅ **Handled**: Both crawlers detect and skip duplicates based on URL

### "Need to track crawl history"
✅ **Solved**: Advanced crawler creates timestamped run directories

## Performance Tips

- Use **Advanced Crawler** for complete gallery coverage
- Adjust `max_categories` and `max_pages_per_category` in `main_advanced.py`
- Monitor crawl progress in timestamped run folders
- Use `reorganize.py` to clean up old basic crawler results

## Notes

- The advanced crawler respects robots.txt and implements proper throttling
- BFS strategy ensures systematic coverage of all gallery categories
- Timestamped runs preserve crawl history and enable incremental updates
- Select tag extraction automatically discovers new gallery categories
- Smart pagination handling prevents missing images within categories
