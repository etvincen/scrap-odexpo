"""
Debug Crawler for Odexpo Gallery - Enhanced with Logging and Single Category Testing
"""

import asyncio
import json
import time
import re
import html
import aiofiles
import logging
import os
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, parse_qs

import aiohttp
from playwright.async_api import async_playwright, Page, Browser

import config
from utils.helpers import (
    is_allowed_domain, 
    download_image, 
    save_metadata, 
    load_metadata,
    get_downloaded_urls_from_metadata,
    clean_text_field,
    fix_dimensions_spacing
)

class DebugCrawler:
    """Debug crawler with enhanced logging and category-specific debugging"""
    
    def __init__(self, target_category: str = None, use_timestamped_run: bool = True):
        self.target_category = target_category
        self.session = None
        self.browser = None
        self.playwright = None
        
        # Setup logging
        if use_timestamped_run:
            self.run_dir = config.get_timestamped_run_dir()
            self.images_dir = f"{self.run_dir}/images"
            self.metadata_file = f"{self.run_dir}/metadata.json"
            self.log_file = f"{self.run_dir}/debug_log.txt"
        else:
            self.run_dir = config.ASSETS_DIR
            self.images_dir = config.IMAGES_DIR
            self.metadata_file = config.METADATA_FILE
            self.log_file = f"{config.ASSETS_DIR}/debug_log.txt"
        
        # Create directories
        Path(self.run_dir).mkdir(parents=True, exist_ok=True)
        Path(self.images_dir).mkdir(parents=True, exist_ok=True)
        
        # Setup dual logging (console + file)
        self.setup_logging()
        
        # Crawl state
        self.visited_urls: Set[str] = set()
        self.downloaded_images: List[Dict] = []
        self.downloaded_urls: Set[str] = set()
        self.categories_found: Set[str] = set()
        self.gallery_categories: List[Dict] = []
        
        self.log(f"📁 Debug crawl run directory: {self.run_dir}")
        if target_category:
            self.log(f"🎯 Target category: {target_category}")

    def setup_logging(self):
        """Setup dual logging to console and file"""
        # Create logger
        self.logger = logging.getLogger('debug_crawler')
        self.logger.setLevel(logging.DEBUG)
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # File handler with detailed formatting
        file_handler = logging.FileHandler(self.log_file, mode='w', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler with simpler formatting
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Detailed formatter for file
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        
        # Simpler formatter for console
        console_formatter = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def log(self, message: str, level: str = "INFO"):
        """Log message to both console and file"""
        if level == "DEBUG":
            self.logger.debug(message)
        elif level == "WARNING":
            self.logger.warning(message)
        elif level == "ERROR":
            self.logger.error(message)
        else:
            self.logger.info(message)

    async def __aenter__(self):
        """Async context manager entry"""
        self.log("🚀 Starting debug crawler...")
        
        # Initialize aiohttp session
        self.session = aiohttp.ClientSession()
        
        # Initialize Playwright
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        
        # Load existing metadata to avoid duplicates
        try:
            existing_metadata = await load_metadata(self.metadata_file)
            self.downloaded_images = existing_metadata
            self.downloaded_urls = get_downloaded_urls_from_metadata(existing_metadata)
            self.log(f"📂 Loaded {len(existing_metadata)} existing images from metadata")
        except:
            self.log("📂 Starting fresh crawl (no existing metadata)")
            
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        if self.session:
            await self.session.close()
        
        self.log(f"💾 Debug log saved to: {self.log_file}")

    async def discover_gallery_page(self, start_url: str) -> Optional[str]:
        """Find the gallery page by looking for the 'galeries' navigation link"""
        self.log(f"🔍 Looking for gallery page from: {start_url}")
        
        page = await self.browser.new_page()
        try:
            await page.goto(start_url, wait_until='networkidle', timeout=10000)  # Reduced timeout
            
            # Look for gallery navigation link
            gallery_links = await page.query_selector_all('a[href*="page=10076"], a[href*="galerie"]')
            
            for link in gallery_links:
                href = await link.get_attribute('href')
                text = await link.inner_text()
                
                if href and ('page=10076' in href or 'galerie' in text.lower()):
                    if href.startswith('/'):
                        gallery_url = urljoin(start_url, href)
                    elif href.startswith('http'):
                        gallery_url = href
                    else:
                        gallery_url = urljoin(start_url, href)
                    self.log(f"🎯 Found gallery page: {gallery_url}")
                    return gallery_url
            
            self.log("⚠️ Gallery page not found in navigation", "WARNING")
            return None
            
        except Exception as e:
            self.log(f"❌ Error during gallery discovery: {e}", "ERROR")
            return None
        finally:
            await page.close()

    async def extract_gallery_categories_simple(self, gallery_url: str) -> List[Dict]:
        """Extract gallery categories and filter for target category if specified"""
        self.log(f"🔍 Extracting categories from gallery page: {gallery_url}")
        
        page = await self.browser.new_page()
        categories = []
        
        try:
            await page.goto(gallery_url, wait_until='networkidle', timeout=10000)  # Reduced timeout
            
            # Find all gallery category links
            category_links = await page.query_selector_all('a[href*="galerie="][href*="ng="]')
            self.log(f"Found {len(category_links)} potential category links")
            
            seen_ids = set()
            for link in category_links:
                href = await link.get_attribute('href')
                text = await link.inner_text()
                
                if href and 'galerie=' in href and 'ng=' in href:
                    # Make absolute URL
                    if href.startswith('/'):
                        full_url = urljoin(gallery_url, href)
                    elif href.startswith('http'):
                        full_url = href
                    else:
                        full_url = urljoin(gallery_url, href)
                    
                    # Extract category info from URL
                    parsed = urlparse(full_url)
                    query_params = parse_qs(parsed.query)
                    
                    galerie_id = query_params.get('galerie', [''])[0]
                    ng_value = query_params.get('ng', [''])[0]
                    
                    if galerie_id and ng_value and galerie_id not in seen_ids:
                        # Clean up the ng value (URL decode and clean)
                        import urllib.parse
                        category_name = urllib.parse.unquote_plus(ng_value).strip()
                        
                        # Filter for target category if specified
                        if self.target_category:
                            if self.target_category.lower() not in category_name.lower():
                                self.log(f"   Skipping category: {category_name} (not target)", "DEBUG")
                                continue
                        
                        categories.append({
                            'name': category_name,
                            'value': galerie_id,
                            'url': full_url,
                            'link_text': text.strip()
                        })
                        
                        seen_ids.add(galerie_id)
                        self.log(f"   ✅ Found category: {category_name} (ID: {galerie_id})")
            
            self.log(f"✅ Found {len(categories)} matching categories")
            return categories
            
        except Exception as e:
            self.log(f"❌ Error extracting categories: {e}", "ERROR")
            return []
        finally:
            await page.close()

    async def _download_image_from_lightbox(self, image_url: str, title: str, painting_type: str, 
                                          dimensions: str, alt: str, source_page: str, page_title: str) -> Optional[Dict]:
        """Download image directly using the URL from lightbox"""
        try:
            self.log(f"🔽 Downloading from lightbox: {image_url}")
            
            async with self.session.get(image_url, timeout=aiohttp.ClientTimeout(total=8)) as response:  # Reduced timeout
                if response.status == 200:
                    content = await response.read()
                    
                    # Extract category from source page URL
                    category_from_url = self._extract_category_from_url(source_page)
                    final_category = category_from_url if category_from_url else 'miscellaneous'
                    
                    self.log(f"   📁 Using category: {final_category}")
                    
                    # Create directory structure
                    from utils.helpers import create_directory_structure_custom
                    images_dir = create_directory_structure_custom(image_url, final_category, self.images_dir)
                    
                    self.log(f"   📂 Images directory: {images_dir}")
                    
                    # Extract filename
                    import os
                    filename = os.path.basename(urlparse(image_url).path)
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
                    
                    self.log(f"   ✅ Saved to: {final_path}")
                    
                    # Return metadata
                    return {
                        'filename': filename,
                        'original_url': image_url,
                        'local_path': final_path,
                        'file_size': len(content),
                        'downloaded_at': time.time(),
                        'source_page': source_page,
                        'page_title': clean_text_field(page_title),
                        'alt_text': clean_text_field(alt),
                        'title': clean_text_field(title),
                        'painting_type': clean_text_field(painting_type),
                        'dimensions': clean_text_field(dimensions),
                        'category': final_category,
                        'crawl_run': self.run_dir
                    }
                else:
                    self.log(f"❌ Failed to download {image_url}: HTTP {response.status}", "WARNING")
                    return None
                    
        except Exception as e:
            self.log(f"❌ Error downloading {image_url}: {e}", "ERROR")
            return None

    async def _download_fallback_image(self, image_url: str, alt: str, source_page: str, page_title: str) -> Optional[Dict]:
        """Download fallback preview image when lightbox fails"""
        try:
            self.log(f"🔽 Downloading fallback preview: {image_url}")
            
            async with self.session.get(image_url, timeout=aiohttp.ClientTimeout(total=8)) as response:  # Reduced timeout
                if response.status == 200:
                    content = await response.read()
                    
                    # Extract category from source page URL
                    category_from_url = self._extract_category_from_url(source_page)
                    final_category = category_from_url if category_from_url else 'miscellaneous'
                    
                    self.log(f"   📁 Using category: {final_category}")
                    
                    # Create directory structure
                    from utils.helpers import create_directory_structure_custom
                    images_dir = create_directory_structure_custom(image_url, final_category, self.images_dir)
                    
                    self.log(f"   📂 Images directory: {images_dir}")
                    
                    # Extract filename
                    import os
                    filename = os.path.basename(urlparse(image_url).path)
                    if not filename:
                        filename = f"preview_{int(time.time())}.jpg"
                    
                    # Add preview prefix to distinguish from high-res
                    base_name, ext = os.path.splitext(filename)
                    preview_filename = f"preview_{base_name}{ext}"
                    
                    # Handle filename conflicts
                    counter = 1
                    final_path = os.path.join(images_dir, preview_filename)
                    
                    while os.path.exists(final_path):
                        new_filename = f"preview_{base_name}_{counter}{ext}"
                        final_path = os.path.join(images_dir, new_filename)
                        counter += 1
                        preview_filename = new_filename
                    
                    # Save image
                    async with aiofiles.open(final_path, 'wb') as f:
                        await f.write(content)
                    
                    self.log(f"   ✅ Saved preview to: {final_path}")
                    
                    # Return metadata
                    return {
                        'filename': preview_filename,
                        'original_url': image_url,
                        'local_path': final_path,
                        'file_size': len(content),
                        'downloaded_at': time.time(),
                        'source_page': source_page,
                        'page_title': clean_text_field(page_title),
                        'alt_text': clean_text_field(alt),
                        'title': '',  # No title available in fallback
                        'painting_type': '',  # No painting type available in fallback
                        'dimensions': '',  # No dimensions available in fallback
                        'category': final_category,
                        'crawl_run': self.run_dir,
                        'is_preview': True  # Mark as preview image
                    }
                else:
                    self.log(f"❌ Failed to download fallback {image_url}: HTTP {response.status}", "WARNING")
                    return None
                    
        except Exception as e:
            self.log(f"❌ Error downloading fallback {image_url}: {e}", "ERROR")
            return None

    def _extract_category_from_url(self, url: str) -> Optional[str]:
        """Extract category name from URL parameters"""
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        # Look for gallery category in ng parameter
        if 'ng' in query_params:
            import urllib.parse
            ng_value = query_params['ng'][0]
            category = urllib.parse.unquote_plus(ng_value).strip()
            self.log(f"   🏷️ Extracted category from URL: {category}", "DEBUG")
            return category
        
        self.log(f"   ⚠️ No category found in URL: {url}", "DEBUG")
        return None

    async def _navigate_slideshow_container(self, page: Page, url: str, page_title: str) -> List[Dict]:
        """
        Special handler for slideshow-container navigation (used in 'presse' category)
        Returns list of downloaded images from the slideshow
        """
        downloaded_images = []
        
        try:
            # Look for slideshow container
            slideshow_container = await page.query_selector('.slideshow-container')
            if not slideshow_container:
                self.log("   📷 No slideshow-container found", "DEBUG")
                return downloaded_images
            
            self.log("   📷 Found slideshow-container, analyzing navigation...")
            
            # Get all thumbnail images to understand the full collection
            all_thumbnail_imgs = await page.query_selector_all('img[src*="pt_"]')
            self.log(f"   🖼️ Found {len(all_thumbnail_imgs)} thumbnail images")
            
            # Extract thumbnail URLs and map them to potential full-res URLs
            thumbnail_mapping = []
            for img in all_thumbnail_imgs:
                src = await img.get_attribute('src')
                if src and 'pt_' in src:
                    # Convert to absolute URL
                    if src.startswith('/'):
                        abs_thumb_src = urljoin(url, src)
                    elif not src.startswith('http'):
                        abs_thumb_src = urljoin(url, src)
                    else:
                        abs_thumb_src = src
                    
                    # Generate potential full-res URL by removing 'pt_' prefix
                    full_res_src = abs_thumb_src.replace('/pt_', '/')
                    
                    thumbnail_mapping.append({
                        'thumbnail': abs_thumb_src,
                        'full_res': full_res_src,
                        'filename': src.split('/')[-1]
                    })
                    
                    self.log(f"   🔗 Mapped: {src} -> {full_res_src.split('/')[-1]}")
            
            self.log(f"   📋 Created {len(thumbnail_mapping)} thumbnail mappings")
            
            # Method 1: Try to download full-resolution versions directly
            for i, mapping in enumerate(thumbnail_mapping):
                try:
                    full_res_url = mapping['full_res']
                    thumbnail_filename = mapping['filename']
                    
                    self.log(f"   🔽 Attempting direct download {i+1}/{len(thumbnail_mapping)}: {full_res_url}")
                    
                    # Check for duplicates
                    if full_res_url not in self.downloaded_urls:
                        downloaded_metadata = await self._download_fallback_image(
                            full_res_url, f"Article/Affiche {i+1}", url, page_title
                        )
                        
                        if downloaded_metadata:
                            downloaded_images.append(downloaded_metadata)
                            self.downloaded_images.append(downloaded_metadata)
                            self.downloaded_urls.add(full_res_url)
                            
                            category = downloaded_metadata.get('category', 'miscellaneous')
                            self.categories_found.add(category)
                            self.log(f"   ✅ Downloaded full-res: {downloaded_metadata['filename']}")
                        else:
                            self.log(f"   ⚠️ Failed to download full-res, trying thumbnail: {thumbnail_filename}")
                            # Fallback to thumbnail if full-res fails
                            if mapping['thumbnail'] not in self.downloaded_urls:
                                thumbnail_metadata = await self._download_fallback_image(
                                    mapping['thumbnail'], f"Thumbnail {i+1}", url, page_title
                                )
                                if thumbnail_metadata:
                                    downloaded_images.append(thumbnail_metadata)
                                    self.downloaded_images.append(thumbnail_metadata)
                                    self.downloaded_urls.add(mapping['thumbnail'])
                                    
                                    category = thumbnail_metadata.get('category', 'miscellaneous')
                                    self.categories_found.add(category)
                                    self.log(f"   ✅ Downloaded thumbnail fallback: {thumbnail_metadata['filename']}")
                    else:
                        self.log(f"   ⏭️ Skipping duplicate full-res: {full_res_url}")
                
                except Exception as e:
                    self.log(f"   ⚠️ Error with mapping {i+1}: {e}", "DEBUG")
                    continue
                
                # Brief pause between downloads
                await asyncio.sleep(0.2)
            
            # Method 2: Also try navigation links for any additional content
            thumbnail_links = await page.query_selector_all('a[href*="num="]')
            self.log(f"   🔗 Found {len(thumbnail_links)} navigation links")
            
            for i, nav_link in enumerate(thumbnail_links[:5]):  # Limit to first 5 to avoid too many requests
                try:
                    href = await nav_link.get_attribute('href')
                    if href and 'num=' in href:
                        # This is a pagination/navigation link
                        if href.startswith('/'):
                            nav_url = urljoin(url, href)
                        elif href.startswith('http'):
                            nav_url = href
                        else:
                            nav_url = urljoin(url, href)
                        
                        self.log(f"   🔗 Checking navigation URL {i+1}: {nav_url}")
                        
                        # Navigate to this URL to get different slideshow content
                        temp_page = await self.browser.new_page()
                        try:
                            await temp_page.goto(nav_url, wait_until='networkidle', timeout=10000)
                            await temp_page.wait_for_timeout(500)
                            
                            # Look for main images that aren't thumbnails
                            nav_main_images = await temp_page.query_selector_all('img[src*="images/"]:not([src*="pt_"])')
                            
                            for img in nav_main_images:
                                src = await img.get_attribute('src')
                                alt = await img.get_attribute('alt') or ""
                                
                                if src and not src.endswith('.gif') and 'pt_' not in src and 'images/' in src:
                                    # Convert to absolute URL
                                    if src.startswith('/'):
                                        abs_src = urljoin(nav_url, src)
                                    elif not src.startswith('http'):
                                        abs_src = urljoin(nav_url, src)
                                    else:
                                        abs_src = src
                                    
                                    self.log(f"   🔽 Navigation page main image: {abs_src}")
                                    
                                    # Check for duplicates
                                    if abs_src not in self.downloaded_urls:
                                        downloaded_metadata = await self._download_fallback_image(
                                            abs_src, alt or f"Navigation image {i+1}", nav_url, page_title
                                        )
                                        
                                        if downloaded_metadata:
                                            downloaded_images.append(downloaded_metadata)
                                            self.downloaded_images.append(downloaded_metadata)
                                            self.downloaded_urls.add(abs_src)
                                            
                                            category = downloaded_metadata.get('category', 'miscellaneous')
                                            self.categories_found.add(category)
                                            self.log(f"   ✅ Downloaded from navigation: {downloaded_metadata['filename']}")
                                    else:
                                        self.log(f"   ⏭️ Skipping duplicate navigation image: {abs_src}")
                        
                        except Exception as e:
                            self.log(f"   ⚠️ Error navigating to {nav_url}: {e}", "WARNING")
                        finally:
                            await temp_page.close()
                        
                        # Brief pause between navigations
                        await asyncio.sleep(0.3)
                
                except Exception as e:
                    self.log(f"   ⚠️ Error with navigation link {i+1}: {e}", "DEBUG")
                    continue
            
            self.log(f"   📷 Slideshow navigation complete: {len(downloaded_images)} images downloaded")
            return downloaded_images
            
        except Exception as e:
            self.log(f"   ❌ Error in slideshow navigation: {e}", "ERROR")
            return downloaded_images

    async def crawl_page_thoroughly(self, url: str) -> Tuple[List[Dict], List[str]]:
        """Crawl a single page thoroughly with enhanced debugging"""
        if url in self.visited_urls:
            self.log(f"⏭️ Already visited: {url}")
            return [], []
            
        if not is_allowed_domain(url):
            self.log(f"🚫 URL not in allowed domain: {url}", "WARNING")
            return [], []
            
        self.log(f"🔍 Crawling page thoroughly: {url}")
        self.visited_urls.add(url)
        
        page = await self.browser.new_page()
        new_images_count = 0
        pagination_links = []
        downloaded_images = []
        
        try:
            # Navigate to page and wait for it to be ready
            await page.goto(url, wait_until='networkidle', timeout=15000)  # Reduced timeout
            
            # Wait a bit more for any remaining content
            await page.wait_for_timeout(500)  # Reduced wait time
            
            # Get page info
            page_title = await page.title()
            self.log(f"✅ Successfully loaded page: {page_title}")
            
            # SPECIAL HANDLING: Check if this is a slideshow-based page (like 'presse')
            slideshow_container = await page.query_selector('.slideshow-container')
            if slideshow_container and self.target_category and 'presse' in self.target_category.lower():
                self.log("🎠 Detected slideshow-container for presse category, using specialized navigation")
                slideshow_images = await self._navigate_slideshow_container(page, url, page_title)
                downloaded_images.extend(slideshow_images)
                new_images_count += len(slideshow_images)
            
            # STANDARD HANDLING: Extract all images using direct DOM queries
            image_elements = await page.query_selector_all('img[src*="images/"]')
            self.log(f"🔬 Found {len(image_elements)} total img elements")
            
            # Filter for gallery images (images in the gallery ID folders)
            for img_element in image_elements:
                src = await img_element.get_attribute('src')
                alt = await img_element.get_attribute('alt') or ""
                
                if src and ('images/' in src or src.startswith('/images/')):
                    # Convert to absolute URL
                    if src.startswith('/'):
                        abs_src = urljoin(url, src)
                    elif src.startswith('http'):
                        abs_src = src
                    else:
                        # Handle relative URLs like "images/27833/..."
                        abs_src = urljoin(url, src)
                    
                    # Check if it's a gallery image (has gallery ID pattern)
                    if re.search(r'images/\d+/', abs_src):
                        self.log(f"🖼️ Processing gallery image: {src} -> {abs_src}")
                        
                        # Check for duplicates first (use absolute URL for duplicate checking)
                        if abs_src in self.downloaded_urls:
                            self.log(f"   ⏭️ Skipping duplicate: {abs_src}")
                            continue
                        
                        # Skip thumbnails if we already processed slideshow
                        if slideshow_container and 'pt_' in src:
                            self.log(f"   ⏭️ Skipping thumbnail (slideshow processed): {abs_src}")
                            continue
                        
                        # Try to click image to get high-res version
                        try:
                            await img_element.click()
                            await page.wait_for_selector('.mfp-img', timeout=2000)  # Much reduced timeout
                            
                            # Get high-res image URL
                            fullres_img = await page.query_selector('.mfp-img')
                            if fullres_img:
                                fullres_src = await fullres_img.get_attribute('src')
                                
                                # Get additional metadata from mfp-title
                                img_title = ""
                                painting_type = ""
                                dimensions = ""
                                
                                mfp_title = await page.query_selector('.mfp-title')
                                if mfp_title:
                                    # Get title from b tag
                                    title_elem = await mfp_title.query_selector('b')
                                    if title_elem:
                                        raw_title = await title_elem.inner_text()
                                        img_title = clean_text_field(raw_title)
                                    
                                    # Get painting type and dimensions from text after br tag
                                    html_content = await mfp_title.inner_html()
                                    parts = html_content.split('<br>')
                                    if len(parts) > 1:
                                        raw_info = parts[1].strip()
                                        info = clean_text_field(raw_info)
                                        info = fix_dimensions_spacing(info)
                                        
                                        # Extract dimensions
                                        dim_match = re.search(r'\b(\d+(?:\.\d+)?\s*x\s*\d+(?:\.\d+)?(?:\s*cm)?)\b', info, re.IGNORECASE)
                                        if dim_match:
                                            raw_dimensions = dim_match.group(1)
                                            dimensions = clean_text_field(fix_dimensions_spacing(raw_dimensions))
                                            painting_type = info.replace(raw_dimensions, '').strip()
                                            painting_type = clean_text_field(painting_type)
                                        else:
                                            painting_type = clean_text_field(info)
                                
                                if fullres_src:
                                    # Convert to absolute URL if needed
                                    if fullres_src.startswith('/'):
                                        fullres_src = urljoin(url, fullres_src)
                                    elif not fullres_src.startswith('http'):
                                        fullres_src = urljoin(url, fullres_src)
                                        
                                    self.log(f"   ✨ Found high-res: {fullres_src}")
                                    self.log(f"      Title: {img_title}")
                                    self.log(f"      Type: {painting_type}")
                                    self.log(f"      Dimensions: {dimensions}")
                                    
                                    # Download image directly while lightbox is open
                                    downloaded_metadata = await self._download_image_from_lightbox(
                                        fullres_src, img_title, painting_type, dimensions, alt, url, page_title
                                    )
                                    
                                    if downloaded_metadata:
                                        downloaded_images.append(downloaded_metadata)
                                        self.downloaded_images.append(downloaded_metadata)
                                        self.downloaded_urls.add(fullres_src)
                                        
                                        # Track categories found
                                        category = downloaded_metadata.get('category', 'miscellaneous')
                                        self.categories_found.add(category)
                                        new_images_count += 1
                                    else:
                                        self.log(f"   ❌ Failed to download high-res: {fullres_src}", "WARNING")
                            
                            # Close lightbox
                            close_btn = await page.query_selector('.mfp-close')
                            if close_btn:
                                await close_btn.click()
                                await asyncio.sleep(0.1)  # Brief pause
                                
                        except Exception as e:
                            self.log(f"   ⚠️ Error with lightbox (expected for {self.target_category}), using fallback: {e}", "WARNING")
                            
                            # ENHANCED FALLBACK: Download the preview image using absolute URL
                            # But skip if we already processed this via slideshow
                            if not (slideshow_container and 'pt_' in src):
                                downloaded_metadata = await self._download_fallback_image(
                                    abs_src, alt, url, page_title  # Use abs_src instead of original src
                                )
                                
                                if downloaded_metadata:
                                    downloaded_images.append(downloaded_metadata)
                                    self.downloaded_images.append(downloaded_metadata)
                                    self.downloaded_urls.add(abs_src)  # Use abs_src for duplicate tracking
                                    
                                    # Track categories found
                                    category = downloaded_metadata.get('category', 'miscellaneous')
                                    self.categories_found.add(category)
                                    new_images_count += 1
                                    self.log(f"   ✅ Downloaded fallback preview: {downloaded_metadata['filename']}")
                                else:
                                    self.log(f"   ❌ Failed to download fallback: {abs_src}", "ERROR")
            
            self.log(f"📥 Downloaded {new_images_count} images from this page")
            
            # Extract pagination links
            pagination_elements = await page.query_selector_all('a[href*="num="]')
            current_category = self._extract_category_from_url(url)
            
            for link in pagination_elements:
                href = await link.get_attribute('href')
                text = await link.inner_text()
                
                if href and text.strip().isdigit():
                    # Make absolute URL
                    if href.startswith('/'):
                        abs_href = urljoin(url, href)
                    elif href.startswith('http'):
                        abs_href = href
                    else:
                        abs_href = urljoin(url, href)
                    
                    # Check if it's for the same category
                    link_category = self._extract_category_from_url(abs_href)
                    if link_category == current_category:
                        pagination_links.append(abs_href)
                        self.log(f"    📄 Found pagination: {text.strip()} -> {abs_href}")
            
            self.log(f"  📄 Found {len(pagination_links)} pagination links")
            
        except Exception as e:
            self.log(f"❌ Error crawling {url}: {e}", "ERROR")
            import traceback
            self.log(f"🔬 Full error traceback:\n{traceback.format_exc()}", "DEBUG")
        finally:
            await page.close()
            
        return downloaded_images, pagination_links

    async def crawl_category_completely(self, category: Dict) -> None:
        """Crawl a single category completely using BFS"""
        category_name = category['name']
        category_url = category['url']
        
        self.log(f"🎨 Starting category: {category_name}")
        self.log(f"📍 Category URL: {category_url}")
        
        # Initialize BFS queue for this category
        category_queue = deque([category_url])
        visited_in_category = set()
        pages_in_category = 0
        
        while category_queue:
            current_url = category_queue.popleft()
            
            if current_url in visited_in_category:
                continue
                
            visited_in_category.add(current_url)
            pages_in_category += 1
            
            self.log(f"📄 Page {pages_in_category} in category '{category_name}'")
            
            # Crawl current page thoroughly
            internal_links, pagination_links = await self.crawl_page_thoroughly(current_url)
            
            # Add pagination URLs to category queue
            new_pagination_count = 0
            for url in pagination_links:
                if url not in visited_in_category:
                    category_queue.append(url)
                    new_pagination_count += 1
            
            if new_pagination_count > 0:
                self.log(f"  ➕ Added {new_pagination_count} new pagination URLs to queue")
                self.log(f"  📊 Queue status: {len(category_queue)} URLs remaining")
            
            # Save metadata after each page
            await save_metadata(self.downloaded_images, self.metadata_file)
            
            # Throttling between pages
            await asyncio.sleep(config.REQUEST_DELAY)
        
        self.log(f"✅ Completed category '{category_name}' - visited {pages_in_category} pages total")

    async def debug_single_category(self, start_url: str = None) -> List[Dict]:
        """Debug crawl for a single category"""
        if not start_url:
            start_url = config.BASE_URL
            
        self.log(f"🚀 Starting debug crawl for category: {self.target_category}")
        self.log(f"🌍 Start URL: {start_url}")
        self.log(f"🎯 Allowed domain: {config.ALLOWED_DOMAIN}")
        
        initial_image_count = len(self.downloaded_images)
        
        # Step 1: Find the gallery page
        gallery_url = await self.discover_gallery_page(start_url)
        if not gallery_url:
            self.log("❌ Could not find gallery page", "ERROR")
            return self.downloaded_images
        
        # Step 2: Extract categories and filter for target
        self.gallery_categories = await self.extract_gallery_categories_simple(gallery_url)
        
        if not self.gallery_categories:
            self.log("❌ No matching categories found", "ERROR")
            return self.downloaded_images
        
        self.log(f"📋 Found {len(self.gallery_categories)} matching categories:")
        for i, cat in enumerate(self.gallery_categories):
            self.log(f"   {i+1}. {cat['name']} (ID: {cat['value']})")
        
        # Step 3: Crawl each matching category
        for category in self.gallery_categories:
            self.log(f"🎨 Processing category: {category['name']}")
            await self.crawl_category_completely(category)
        
        new_images_this_session = len(self.downloaded_images) - initial_image_count
        self.log(f"🎉 Debug crawl completed!")
        self.log(f"Categories processed: {len(self.gallery_categories)}")
        self.log(f"New images downloaded: {new_images_this_session}")
        self.log(f"Total images in collection: {len(self.downloaded_images)}")
        
        if self.categories_found:
            self.log(f"📁 Categories found: {', '.join(sorted(self.categories_found))}")
        
        # Final save
        await save_metadata(self.downloaded_images, self.metadata_file)
        self.log(f"💾 Metadata saved to: {self.metadata_file}")
        
        return self.downloaded_images

async def main():
    """Main debug function"""
    print("🐛 Debug Crawler for Odexpo Gallery")
    print("=" * 50)
    
    # Get target category from user
    target_category = input("Enter category name to debug (e.g., 'presse'): ").strip()
    
    if not target_category:
        print("❌ No category specified")
        return
    
    print(f"🎯 Debugging category: {target_category}")
    print("=" * 50)
    
    try:
        async with DebugCrawler(target_category=target_category, use_timestamped_run=True) as crawler:
            await crawler.debug_single_category()
            
            print("\n" + "=" * 50)
            print("🎉 Debug session completed!")
            print(f"📁 Results saved in: {crawler.run_dir}")
            print(f"📄 Debug log: {crawler.log_file}")
            print("=" * 50)
            
    except KeyboardInterrupt:
        print("\n👋 Debug session cancelled by user")
    except Exception as e:
        print(f"\n❌ Error during debug session: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 