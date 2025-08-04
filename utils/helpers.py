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
import urllib.parse
import time

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
    """Clean description text to create a valid folder name"""
    if not description:
        return "miscellaneous"
    
    # Remove HTML tags if any
    import re
    cleaned = re.sub(r'<[^>]+>', '', description)
    
    # Remove extra whitespace, tabs, newlines
    cleaned = re.sub(r'\s+', ' ', cleaned.strip())
    
    # SIMPLIFIED: Just take the first meaningful word/phrase
    # Split by common separators and take first part
    parts = re.split(r'[,\n\r\t]+', cleaned)
    if parts:
        first_part = parts[0].strip()
        if first_part:
            cleaned = first_part
    
    # Replace problematic characters for folder names
    cleaned = re.sub(r'[<>:"/\\|?*]', '_', cleaned)
    cleaned = re.sub(r'[àáâãäå]', 'a', cleaned)
    cleaned = re.sub(r'[èéêë]', 'e', cleaned)
    cleaned = re.sub(r'[ìíîï]', 'i', cleaned)
    cleaned = re.sub(r'[òóôõö]', 'o', cleaned)
    cleaned = re.sub(r'[ùúûü]', 'u', cleaned)
    cleaned = re.sub(r'[ç]', 'c', cleaned)
    
    # Convert to lowercase and replace spaces with underscores
    cleaned = cleaned.lower().replace(' ', '_')
    
    # Remove multiple underscores
    cleaned = re.sub(r'_+', '_', cleaned)
    
    # Remove leading/trailing underscores
    cleaned = cleaned.strip('_')
    
    # Ensure it's not empty and not too long
    if not cleaned or len(cleaned) < 2:
        return "miscellaneous"
    
    return cleaned[:50]  # Limit length

def create_directory_structure(image_url: str, description: str = "") -> str:
    """Create directory structure based on description content"""
    return create_directory_structure_custom(image_url, description, config.IMAGES_DIR)

def is_duplicate_image(image_url: str, downloaded_urls: Set[str]) -> bool:
    """Check if image URL has already been downloaded"""
    return image_url in downloaded_urls

async def download_image(session: aiohttp.ClientSession, image_info: Dict, base_url: str, downloaded_urls: Set[str], custom_images_dir: str = None) -> Optional[Dict]:
    """Download image and return metadata with duplicate checking"""
    image_url = image_info.get('src', '')
    
    if not image_url:
        print("⚠️  No image URL found")
        return None
    
    # Convert relative URLs to absolute
    if image_url.startswith('/') or not image_url.startswith('http'):
        if image_url.startswith('//'):
            image_url = 'https:' + image_url
        elif image_url.startswith('/'):
            image_url = urljoin(base_url, image_url)
        else:
            image_url = urljoin(base_url, image_url)
    
    # Check for duplicates
    if is_duplicate_image(image_url, downloaded_urls):
        print(f"Skipping duplicate image: {image_url}")
        return None
    
    try:
        print(f"Downloading: {image_url}")
        
        async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
            if response.status == 200:
                content = await response.read()
                
                # DIAGNOSTIC: Log image info details
                print(f"🔬 CATEGORY DIAGNOSTIC for {image_url}:")
                print(f"   - Source page: {image_info.get('source_page', 'UNKNOWN')}")
                print(f"   - Original description: {repr(image_info.get('desc', ''))}")
                print(f"   - Image alt: {repr(image_info.get('alt', ''))}")
                
                # Clean description for folder creation
                description = image_info.get('desc', '') or image_info.get('alt', '') or 'No description'
                cleaned_description = clean_description_for_folder(description)
                
                # DIAGNOSTIC: Check if we can extract category from source page URL
                source_page = image_info.get('source_page', '')
                category_from_url = None
                if 'ng=' in source_page:
                    try:
                        parsed = urllib.parse.urlparse(source_page)
                        query_params = urllib.parse.parse_qs(parsed.query)
                        ng_value = query_params.get('ng', [''])[0]
                        if ng_value:
                            category_from_url = urllib.parse.unquote_plus(ng_value).strip()
                    except Exception as e:
                        print(f"   - Error extracting category from URL: {e}")
                
                print(f"   - Category from URL: {repr(category_from_url)}")
                print(f"   - Cleaned description: {repr(cleaned_description)}")
                
                # Use category from URL if available, otherwise use cleaned description
                final_category = category_from_url if category_from_url else cleaned_description
                print(f"   - Final category: {repr(final_category)}")
                
                # Create directory structure
                if custom_images_dir:
                    images_dir = create_directory_structure_custom(image_url, final_category, custom_images_dir)
                else:
                    images_dir = create_directory_structure(image_url, final_category)
                
                # Extract filename
                filename = os.path.basename(urllib.parse.urlparse(image_url).path)
                if not filename:
                    filename = f"image_{int(time.time())}.jpg"
                
                # Handle filename conflicts
                base_name, ext = os.path.splitext(filename)
                counter = 1
                final_path = os.path.join(images_dir, filename)
                
                while os.path.exists(final_path):
                    new_filename = f"{base_name}_{counter}{ext}"
                    final_path = os.path.join(images_dir, new_filename)
                    counter += 1
                    filename = new_filename
                
                # Save image
                async with aiofiles.open(final_path, 'wb') as f:
                    await f.write(content)
                
                # Mark as downloaded
                downloaded_urls.add(image_url)
                
                # Return metadata
                metadata = {
                    'filename': filename,
                    'original_url': image_url,
                    'local_path': final_path,
                    'file_size': len(content),
                    'downloaded_at': time.time(),
                    'source_page': image_info.get('source_page', ''),
                    'page_title': image_info.get('page_title', ''),
                    'alt_text': image_info.get('alt', ''),
                    'description': description,
                    'cleaned_description': cleaned_description,
                    'category': final_category,  # This is the key field for organization
                    'crawl_run': image_info.get('crawl_run', ''),
                    'score': image_info.get('score', 0)
                }
                
                print(f"✅ Downloaded: {filename} → {final_category}")
                return metadata
            else:
                print(f"❌ Failed to download {image_url}: HTTP {response.status}")
                return None
                
    except Exception as e:
        print(f"❌ Error downloading {image_url}: {e}")
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

def create_directory_structure_custom(image_url: str, description: str = "", base_images_dir: str = None) -> str:
    """Create directory structure based on description content with custom base directory"""
    try:
        # Use description to create category-based subfolder
        category_folder = clean_description_for_folder(description)
        
        # Use custom base directory if provided
        images_dir = base_images_dir if base_images_dir else config.IMAGES_DIR
        
        # Create the directory path
        subdir = os.path.join(images_dir, category_folder)
        Path(subdir).mkdir(parents=True, exist_ok=True)
        
        return subdir
    except Exception:
        # Fallback to main images directory
        images_dir = base_images_dir if base_images_dir else config.IMAGES_DIR
        Path(images_dir).mkdir(parents=True, exist_ok=True)
        return images_dir 