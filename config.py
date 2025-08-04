"""
Configuration file for Odexpo Gallery Scraper
"""

# Domain restrictions
ALLOWED_DOMAIN = "fabienne-vincent.odexpo.com"
BASE_URL = f"https://{ALLOWED_DOMAIN}"

# Crawler settings
MAX_CONCURRENT_REQUESTS = 3  # Basic throttling
REQUEST_DELAY = 0.5  # Delay between requests in seconds
TIMEOUT = 30  # Request timeout in seconds

# File paths
ASSETS_DIR = "assets"
IMAGES_DIR = f"{ASSETS_DIR}/images"
METADATA_FILE = f"{ASSETS_DIR}/metadata.json"

# Image settings
SUPPORTED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
MAX_IMAGE_SIZE = 50 * 1024 * 1024  # 50MB max per image 