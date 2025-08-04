"""
Configuration file for Odexpo Gallery Scraper
"""

from datetime import datetime

# Domain restrictions
ALLOWED_DOMAIN = "fabienne-vincent.odexpo.com"
BASE_URL = f"https://{ALLOWED_DOMAIN}"
GALLERY_URL = f"https://{ALLOWED_DOMAIN}/default.asp?page=10076"  # Direct gallery page

# Crawler settings
MAX_CONCURRENT_REQUESTS = 3  # Basic throttling
REQUEST_DELAY = 0.5  # Delay between requests in seconds
TIMEOUT = 30  # Request timeout in seconds

# File paths
ASSETS_DIR = "assets"
def get_timestamped_run_dir():
    """Generate timestamped directory for current crawl run"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{ASSETS_DIR}/crawl_runs/{timestamp}"

IMAGES_DIR = f"{ASSETS_DIR}/images"
METADATA_FILE = f"{ASSETS_DIR}/metadata.json"

# Image settings
SUPPORTED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
MAX_IMAGE_SIZE = 50 * 1024 * 1024  # 50MB max per image

# Gallery-specific settings
GALLERY_SELECT_CLASS = "form-control-comb classicomb"
PAGINATION_KEYWORDS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]  # Numbered pagination
CATEGORY_URL_PATTERNS = ["galerie=", "ng="]
GALLERY_NAVIGATION_KEYWORDS = ["galerie", "gallery", "portfolio", "œuvres", "oeuvres", "art"] 