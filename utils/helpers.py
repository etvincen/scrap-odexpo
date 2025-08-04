"""
Utility functions for the Odexpo Gallery Scraper
"""

import os
import asyncio
import aiohttp
import aiofiles
from urllib.parse import urljoin, urlparse
from pathlib import Path
import json
from typing import Dict, List, Optional
import config

def is_allowed_domain(url: str) -> bool:
    """Check if URL belongs to allowed domain"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        return domain == config.ALLOWED_DOMAIN or domain == f"www.{config.ALLOWED_DOMAIN}"
    except Exception:
        return False

def is_image_url(url: str) -> bool:
    """Check if URL points to an image file"""
    try:
        parsed = urlparse(url)
        path = parsed.path.lower()
        return any(path.endswith(ext) for ext in config.SUPPORTED_IMAGE_EXTENSIONS)
    except Exception:
        return False

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file system storage"""
    # Replace problematic characters
    for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
        filename = filename.replace(char, '_')
    return filename[:255]  # Limit length

def create_directory_structure(url: str) -> str:
    """Create directory structure based on URL path"""
    try:
        parsed = urlparse(url)
        path_parts = [part for part in parsed.path.split('/') if part]
        
        # Create subdirectory structure
        subdir = os.path.join(config.IMAGES_DIR, *path_parts[:-1]) if path_parts[:-1] else config.IMAGES_DIR
        Path(subdir).mkdir(parents=True, exist_ok=True)
        
        return subdir
    except Exception:
        # Fallback to main images directory
        Path(config.IMAGES_DIR).mkdir(parents=True, exist_ok=True)
        return config.IMAGES_DIR

async def download_image(session: aiohttp.ClientSession, image_info: Dict, base_url: str) -> Optional[Dict]:
    """Download an image and return metadata"""
    try:
        image_url = image_info.get('src', '')
        if not image_url:
            return None
            
        # Convert relative URLs to absolute
        if image_url.startswith('//'):
            image_url = 'https:' + image_url
        elif image_url.startswith('/'):
            image_url = urljoin(base_url, image_url)
        elif not image_url.startswith(('http://', 'https://')):
            image_url = urljoin(base_url, image_url)
        
        # Check if image URL is from allowed domain
        if not is_allowed_domain(image_url):
            print(f"Skipping external image: {image_url}")
            return None
            
        # Check if it's actually an image
        if not is_image_url(image_url):
            print(f"Skipping non-image URL: {image_url}")
            return None
            
        print(f"Downloading: {image_url}")
        
        async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=config.TIMEOUT)) as response:
            if response.status == 200:
                content = await response.read()
                
                # Check file size
                if len(content) > config.MAX_IMAGE_SIZE:
                    print(f"Image too large ({len(content)} bytes): {image_url}")
                    return None
                
                # Create directory structure
                save_dir = create_directory_structure(image_url)
                
                # Generate filename
                filename = os.path.basename(urlparse(image_url).path)
                if not filename or '.' not in filename:
                    filename = f"image_{hash(image_url) % 10000}.jpg"
                filename = sanitize_filename(filename)
                
                file_path = os.path.join(save_dir, filename)
                
                # Save image
                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(content)
                
                # Return metadata
                return {
                    'original_url': image_url,
                    'local_path': file_path,
                    'filename': filename,
                    'size_bytes': len(content),
                    'alt_text': image_info.get('alt', ''),
                    'title': image_info.get('title', ''),
                    'description': image_info.get('desc', ''),
                    'score': image_info.get('score', 0),
                    'width': image_info.get('width'),
                    'height': image_info.get('height'),
                }
            else:
                print(f"Failed to download {image_url}: HTTP {response.status}")
                return None
                
    except Exception as e:
        print(f"Error downloading image {image_url}: {e}")
        return None

async def save_metadata(metadata: List[Dict], filename: str = config.METADATA_FILE):
    """Save metadata to JSON file"""
    try:
        Path(config.ASSETS_DIR).mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(filename, 'w') as f:
            await f.write(json.dumps(metadata, indent=2, ensure_ascii=False))
        print(f"Metadata saved to {filename}")
    except Exception as e:
        print(f"Error saving metadata: {e}")

async def load_metadata(filename: str = config.METADATA_FILE) -> List[Dict]:
    """Load metadata from JSON file"""
    try:
        if os.path.exists(filename):
            async with aiofiles.open(filename, 'r') as f:
                content = await f.read()
                return json.loads(content)
    except Exception as e:
        print(f"Error loading metadata: {e}")
    return [] 