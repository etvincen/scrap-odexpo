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
import re
from typing import Dict, List, Optional, Set
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

def clean_description_for_folder(description: str) -> str:
    """
    Clean description text to create a suitable folder name
    Removes tabs, newlines, extra spaces and extracts the main category
    """
    if not description:
        return "miscellaneous"
    
    # Remove tabs, newlines, and extra whitespace
    cleaned = re.sub(r'[\t\n\r]+', ' ', description)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # Split by common separators and look for category names
    lines = cleaned.split('\n')
    candidates = []
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines or very long lines (likely descriptions)
        if not line or len(line) > 100:
            continue
            
        # Look for short, meaningful category names
        # Common patterns in French gallery names
        if len(line) < 50 and (
            line.isupper() or  # All caps like "FAUVES", "ANIMAUX"
            any(word in line.upper() for word in [
                'ANIMAUX', 'PORTRAITS', 'FAUVES', 'PASTEL', 'ACRYLIQUE', 
                'ORIENT', 'AFRIQUE', 'ASIE', 'ABSTRAITS', 'NATURE', 
                'OISEAUX', 'ENFANCE', 'DIVERS', 'COMMANDES', 'RIZIERES'
            ])
        ):
            candidates.append(line.strip())
    
    # Take the first candidate or extract from the beginning
    if candidates:
        category_name = candidates[0]
    else:
        # Fallback: take first few meaningful words
        words = [word for word in cleaned.split()[:5] if len(word) > 2]
        category_name = ' '.join(words[:3]) if words else cleaned[:50]
    
    # Clean for folder name - preserve French characters
    # Allow letters, numbers, spaces, hyphens, apostrophes
    folder_name = re.sub(r'[^\w\s\'-àâäéèêëïîôöùûüÿñç]', '', category_name, flags=re.IGNORECASE)
    
    # Replace spaces with underscores and clean up
    folder_name = re.sub(r'\s+', '_', folder_name)
    folder_name = folder_name.lower().strip('_')
    
    # Handle special cases and clean up common issues
    folder_name = folder_name.replace("'", "")  # Remove apostrophes
    folder_name = re.sub(r'_+', '_', folder_name)  # Multiple underscores to single
    
    # Ensure we have something meaningful
    if len(folder_name) < 2:
        return "miscellaneous"
    
    # Limit length for filesystem compatibility
    return folder_name[:50]

def create_directory_structure(image_url: str, description: str = "") -> str:
    """Create directory structure based on description content"""
    try:
        # Use description to create category-based subfolder
        category_folder = clean_description_for_folder(description)
        
        # Create the directory path
        subdir = os.path.join(config.IMAGES_DIR, category_folder)
        Path(subdir).mkdir(parents=True, exist_ok=True)
        
        return subdir
    except Exception:
        # Fallback to main images directory
        Path(config.IMAGES_DIR).mkdir(parents=True, exist_ok=True)
        return config.IMAGES_DIR

def is_duplicate_image(image_url: str, downloaded_urls: Set[str]) -> bool:
    """Check if image URL has already been downloaded"""
    return image_url in downloaded_urls

async def download_image(session: aiohttp.ClientSession, image_info: Dict, base_url: str, downloaded_urls: Set[str]) -> Optional[Dict]:
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
        
        # Check for duplicates
        if is_duplicate_image(image_url, downloaded_urls):
            print(f"Skipping duplicate image: {image_url}")
            return None
            
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
                
                # Get description for folder structure
                description = image_info.get('desc', '')
                
                # Create directory structure based on description
                save_dir = create_directory_structure(image_url, description)
                
                # Generate filename
                filename = os.path.basename(urlparse(image_url).path)
                if not filename or '.' not in filename:
                    filename = f"image_{hash(image_url) % 10000}.jpg"
                filename = sanitize_filename(filename)
                
                file_path = os.path.join(save_dir, filename)
                
                # Handle filename conflicts within the same folder
                counter = 1
                original_filename = filename
                while os.path.exists(file_path):
                    name, ext = os.path.splitext(original_filename)
                    filename = f"{name}_{counter}{ext}"
                    file_path = os.path.join(save_dir, filename)
                    counter += 1
                
                # Save image
                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(content)
                
                # Add to downloaded URLs set
                downloaded_urls.add(image_url)
                
                # Clean description for metadata
                cleaned_description = clean_description_for_folder(description)
                
                # Return metadata
                return {
                    'original_url': image_url,
                    'local_path': file_path,
                    'filename': filename,
                    'size_bytes': len(content),
                    'alt_text': image_info.get('alt', ''),
                    'title': image_info.get('title', ''),
                    'description': description,
                    'cleaned_description': cleaned_description,
                    'category': cleaned_description,
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

def get_downloaded_urls_from_metadata(metadata: List[Dict]) -> Set[str]:
    """Extract downloaded URLs from existing metadata to avoid duplicates"""
    return {item['original_url'] for item in metadata if 'original_url' in item} 