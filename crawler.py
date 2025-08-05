"""
Advanced crawler for Odexpo Gallery Scraper using Playwright
Direct DOM manipulation for old jQuery websites
"""

import asyncio
import json
import time
import re
import html
import aiofiles
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
    get_downloaded_urls_from_metadata
)

def clean_text_field(text: str) -> str:
    """Clean text field by normalizing whitespace and decoding HTML entities"""
    if not text:
        return ""
    
    # Decode HTML entities (like &nbsp;, &amp;, etc.)
    text = html.unescape(text)
    
    # Remove any remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Normalize whitespace: replace multiple spaces/tabs/newlines with single space
    text = re.sub(r'\s+', ' ', text)
    
    # Trim leading and trailing whitespace
    text = text.strip()
    
    return text

def fix_dimensions_spacing(text: str) -> str:
    """Fix spacing issues in dimensions like 'x5 0' -> 'x50'"""
    if not text:
        return ""
    
    # Handle cases like "40 x5 0 cm" -> "40 x50 cm"
    # Look for pattern like "x followed by digit space digit"
    text = re.sub(r'x(\d+)\s+(\d+)', r'x\1\2', text)
    
    # Also handle "x 5 0" -> "x50"
    text = re.sub(r'x\s+(\d+)\s+(\d+)', r'x\1\2', text)
    
    return text

class PlaywrightOdexpoGalleryCrawler:
    """
    Advanced gallery crawler using Playwright for direct DOM control
    """
    
    def __init__(self, use_timestamped_run: bool = True):
        self.session = None
        self.browser = None
        self.playwright = None
        
        # Timestamped run directory
        if use_timestamped_run:
            self.run_dir = config.get_timestamped_run_dir()
            self.images_dir = f"{self.run_dir}/images"
            self.metadata_file = f"{self.run_dir}/metadata.json"
        else:
            self.run_dir = config.ASSETS_DIR
            self.images_dir = config.IMAGES_DIR
            self.metadata_file = config.METADATA_FILE
        
        # Create directories
        Path(self.run_dir).mkdir(parents=True, exist_ok=True)
        Path(self.images_dir).mkdir(parents=True, exist_ok=True)
        
        # Crawl state
        self.visited_urls: Set[str] = set()
        self.downloaded_images: List[Dict] = []
        self.downloaded_urls: Set[str] = set()
        self.categories_found: Set[str] = set()
        self.gallery_categories: List[Dict] = []
        
        print(f"📁 Crawl run directory: {self.run_dir}")

    async def __aenter__(self):
        """Async context manager entry"""
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
            print(f"📂 Loaded {len(existing_metadata)} existing images from metadata")
        except:
            print("📂 Starting fresh crawl (no existing metadata)")
            
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        if self.session:
            await self.session.close()

    async def discover_gallery_page(self, start_url: str) -> Optional[str]:
        """Find the gallery page by looking for the 'galeries' navigation link"""
        print(f"🔍 Looking for gallery page from: {start_url}")
        
        page = await self.browser.new_page()
        try:
            await page.goto(start_url, wait_until='networkidle')
            
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
                        # Handle relative URLs like "default.asp?page=10076&lg="
                        gallery_url = urljoin(start_url, href)
                    print(f"🎯 Found gallery page: {gallery_url}")
                    return gallery_url
            
            print("⚠️  Gallery page not found in navigation")
            return None
            
        except Exception as e:
            print(f"❌ Error during gallery discovery: {e}")
            return None
        finally:
            await page.close()

    async def extract_gallery_categories_simple(self, gallery_url: str) -> List[Dict]:
        """Extract gallery categories directly from gallery page links using ng parameter"""
        print(f"🔍 Extracting categories from gallery page: {gallery_url}")
        
        page = await self.browser.new_page()
        categories = []
        
        try:
            await page.goto(gallery_url, wait_until='networkidle')
            
            # Find all gallery category links
            category_links = await page.query_selector_all('a[href*="galerie="][href*="ng="]')
            print(f"Found {len(category_links)} potential category links")
            
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
                        # Handle relative URLs like "default.asp?galerie=..."
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
                        
                        categories.append({
                            'name': category_name,
                            'value': galerie_id,
                            'url': full_url,
                            'link_text': text.strip()
                        })
                        
                        seen_ids.add(galerie_id)
                        print(f"   Found category: {category_name} (ID: {galerie_id})")
            
            print(f"✅ Found {len(categories)} unique gallery categories")
            return categories
            
        except Exception as e:
            print(f"❌ Error extracting categories: {e}")
            return []
        finally:
            await page.close()

    async def _download_image_from_lightbox(self, image_url: str, title: str, painting_type: str, 
                                          dimensions: str, alt: str, source_page: str, page_title: str) -> Optional[Dict]:
        """Download image directly using the URL from lightbox, avoiding duplicate HTTP requests"""
        try:
            print(f"🔽 Downloading directly: {image_url}")
            
            async with self.session.get(image_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    content = await response.read()
                    
                    # Extract category from source page URL
                    category_from_url = self._extract_category_from_url(source_page)
                    final_category = category_from_url if category_from_url else 'miscellaneous'
                    
                    # Create directory structure
                    from utils.helpers import create_directory_structure_custom
                    images_dir = create_directory_structure_custom(image_url, final_category, self.images_dir)
                    
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
                    print(f"❌ Failed to download {image_url}: HTTP {response.status}")
                    return None
                    
        except Exception as e:
            print(f"❌ Error downloading {image_url}: {e}")
            return None

    def _extract_category_from_url(self, url: str) -> Optional[str]:
        """Extract category name from URL parameters"""
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        # Look for gallery category in ng parameter
        if 'ng' in query_params:
            import urllib.parse
            ng_value = query_params['ng'][0]
            return urllib.parse.unquote_plus(ng_value).strip()
        
        return None

    def _get_pagination_urls(self, url: str, page: Page) -> List[str]:
        """Extract pagination URLs for the current category"""
        # This will be implemented when we have the page object
        # For now, return empty list - we'll handle pagination differently
        return []

    async def crawl_page_thoroughly(self, url: str) -> Tuple[List[Dict], List[str]]:
        """
        Crawl a single page thoroughly using Playwright
        Returns: (images, pagination_links)
        """
        if url in self.visited_urls:
            print(f"Already visited: {url}")
            return [], []
            
        if not is_allowed_domain(url):
            print(f"URL not in allowed domain: {url}")
            return [], []
            
        print(f"🔍 Crawling page thoroughly: {url}")
        self.visited_urls.add(url)
        
        print(f"🔬 DIAGNOSTIC: Starting Playwright crawl of {url}")
        
        page = await self.browser.new_page()
        new_images_count = 0
        pagination_links = []
        
        try:
            # Navigate to page and wait for it to be ready
            await page.goto(url, wait_until='networkidle', timeout=60000)
            
            # Wait a bit more for any remaining content
            await page.wait_for_timeout(2000)
            
            # Get page info
            page_title = await page.title()
            print(f"✅ Successfully crawled: {url}")
            print(f"Page title: {page_title}")
            
            # DIAGNOSTIC: Analyze page content
            content = await page.content()
            print(f"🔬 DIAGNOSTIC: Page analysis:")
            print(f"   - HTML length: {len(content)} chars")
            
            # Extract all images using direct DOM queries
            image_elements = await page.query_selector_all('img[src*="images/"]')
            print(f"🔬 DIAGNOSTIC: Found {len(image_elements)} total img elements")
            
            # Filter for gallery images (images in the gallery ID folders)
            gallery_images = []
            
            for img_element in image_elements:
                src = await img_element.get_attribute('src')
                alt = await img_element.get_attribute('alt') or ""
                
                if src and ('images/' in src or src.startswith('/images/')):
                    # Convert to absolute URL
                    if src.startswith('/'):
                        abs_src = urljoin(url, src)
                    else:
                        abs_src = src
                    
                    # Check if it's a gallery image (has gallery ID pattern)
                    if re.search(r'images/\d+/', abs_src):
                        # Click image to get high-res version
                        print(f"🖱️  Getting high-res version for: {abs_src}")
                        try:
                            await img_element.click()
                            await page.wait_for_selector('.mfp-img', timeout=5000)
                            
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
                                    # Split content after <br> tag
                                    parts = html_content.split('<br>')
                                    if len(parts) > 1:
                                        raw_info = parts[1].strip()
                                        # Clean the text first
                                        info = clean_text_field(raw_info)
                                        # Fix spacing issues in dimensions
                                        info = fix_dimensions_spacing(info)
                                        
                                        # Improved regex for dimensions that handles spacing issues
                                        # Matches patterns like "40 x50 cm", "40x50", "40 x 50", etc.
                                        dim_match = re.search(r'\b(\d+(?:\.\d+)?\s*x\s*\d+(?:\.\d+)?(?:\s*cm)?)\b', info, re.IGNORECASE)
                                        if dim_match:
                                            raw_dimensions = dim_match.group(1)
                                            # Apply both fixes to the extracted dimensions
                                            dimensions = clean_text_field(fix_dimensions_spacing(raw_dimensions))
                                            # Remove dimensions from painting_type
                                            painting_type = info.replace(raw_dimensions, '').strip()
                                            painting_type = clean_text_field(painting_type)
                                        else:
                                            painting_type = clean_text_field(info)
                                
                                if fullres_src:
                                    # Convert to absolute URL if needed
                                    if fullres_src.startswith('/'):
                                        fullres_src = urljoin(url, fullres_src)
                                    elif not fullres_src.startswith('http'):
                                        fullres_src = urljoin(url, '/' + fullres_src)
                                        
                                    print(f"   ✨ Found high-res: {fullres_src}")
                                    print(f"      Title: {img_title}")
                                    print(f"      Type: {painting_type}")
                                    print(f"      Dimensions: {dimensions}")
                                    
                                    # Check for duplicates before downloading
                                    if fullres_src not in self.downloaded_urls:
                                        # Download image directly while lightbox is open
                                        downloaded_metadata = await self._download_image_from_lightbox(
                                            fullres_src, img_title, painting_type, dimensions, alt, url, page_title
                                        )
                                        
                                        if downloaded_metadata:
                                            gallery_images.append(downloaded_metadata)
                                            self.downloaded_images.append(downloaded_metadata)
                                            self.downloaded_urls.add(fullres_src)
                                            
                                            # Track categories found
                                            category = downloaded_metadata.get('category', 'miscellaneous')
                                            self.categories_found.add(category)
                                            print(f"   ✅ Downloaded directly: {downloaded_metadata['filename']}")
                                        else:
                                            print(f"   ❌ Failed to download: {fullres_src}")
                                    else:
                                        print(f"   ⏭️  Skipping duplicate: {fullres_src}")
                            
                            # Close lightbox
                            close_btn = await page.query_selector('.mfp-close')
                            if close_btn:
                                await close_btn.click()
                                await asyncio.sleep(0.2)  # Reduced pause between images
                                
                        except Exception as e:
                            print(f"   ⚠️  Error getting high-res version: {e}")
                            # Fallback to preview version if high-res fails
                            gallery_images.append({
                                'src': abs_src,
                                'alt': clean_text_field(alt),
                                'title': '',  # No title available in fallback
                                'painting_type': '',  # No painting type available in fallback
                                'dimensions': '',  # No dimensions available in fallback
                                'desc': clean_text_field(alt),
                                'source_page': url,
                                'page_title': clean_text_field(page_title),
                                'found_at': time.time(),
                                'crawl_run': self.run_dir
                            })
            
            print(f"🔬 DIAGNOSTIC: Found {len(gallery_images)} gallery images (filtered)")
            if len(gallery_images) < 10:
                print(f"🔬 SUSPICIOUS: Only {len(gallery_images)} gallery images found")
                
                # Check HTML for all img tags with gallery pattern
                all_gallery_imgs = re.findall(r'<img[^>]*src=["\']([^"\']*images/\d+/[^"\']*)["\'][^>]*>', content, re.IGNORECASE)
                print(f"🔬 HTML Analysis: Found {len(all_gallery_imgs)} gallery img tags via regex")
                
                if len(all_gallery_imgs) > len(gallery_images):
                    print(f"   🚨 DISCREPANCY: HTML has {len(all_gallery_imgs)} gallery images but we only extracted {len(gallery_images)}")
                    # Show examples
                    for i, img_src in enumerate(all_gallery_imgs[:3]):
                        print(f"      Example {i+1}: {img_src}")
            
            print(f"Found {len(gallery_images)} images on this page")
            
            # Images are now downloaded directly in the lightbox loop above
            # No need for separate processing loop
            new_images_count = len(gallery_images)
            
            print(f"📥 Downloaded {new_images_count} new images from this page")
            print(f"🔬 DIAGNOSTIC: Expected vs Actual - Got: {new_images_count} images")
            
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
                        # Handle relative URLs like "default.asp?mdp=..."
                        abs_href = urljoin(url, href)
                    
                    # Check if it's for the same category
                    link_category = self._extract_category_from_url(abs_href)
                    if link_category == current_category:
                        pagination_links.append(abs_href)
                        print(f"    Found pagination: {text.strip()} -> {abs_href}")
            
            print(f"  - {len(pagination_links)} pagination links")
            
        except Exception as e:
            print(f"Error crawling {url}: {e}")
            import traceback
            print(f"🔬 DIAGNOSTIC: Full error traceback:")
            traceback.print_exc()
        finally:
            await page.close()
            
        return [], pagination_links  # Return empty list for internal links, just pagination

    async def crawl_category_completely(self, category: Dict) -> None:
        """
        Crawl a single category completely using BFS until all pages are exhausted
        """
        category_name = category['name']
        category_url = category['url']
        
        print(f"Category URL: {category_url}")
        
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
            
            print(f"\n📄 Page {pages_in_category} in category '{category_name}'")
            
            # Crawl current page thoroughly
            internal_links, pagination_links = await self.crawl_page_thoroughly(current_url)
            
            # Add pagination URLs to category queue
            new_pagination_count = 0
            for url in pagination_links:
                if url not in visited_in_category:
                    category_queue.append(url)
                    new_pagination_count += 1
            
            if new_pagination_count > 0:
                print(f"  Added {new_pagination_count} new pagination URLs to queue")
                print(f"  Queue status: {len(category_queue)} URLs remaining")
            
            # Save metadata after each page
            await save_metadata(self.downloaded_images, self.metadata_file)
            
            # Throttling between pages
            await asyncio.sleep(config.REQUEST_DELAY)
        
        print(f"✅ Completed category '{category_name}' - visited {pages_in_category} pages total")

    async def crawl_website_advanced(self, start_url: str = None, max_categories: Optional[int] = 3) -> List[Dict]:
        """
        Simplified advanced website crawling using direct Playwright navigation
        """
        if not start_url:
            start_url = config.BASE_URL
            
        print(f"🚀 Starting advanced website crawl from: {start_url}")
        print(f"Allowed domain: {config.ALLOWED_DOMAIN}")
        print(f"Max categories: {max_categories if max_categories != 'all' else 'all'}")
        print(f"Strategy: Direct Playwright + DOM extraction")
        
        initial_image_count = len(self.downloaded_images)
        
        # Step 1: Find the gallery page directly
        gallery_url = await self.discover_gallery_page(start_url)
        if not gallery_url:
            print("❌ Could not find gallery page")
            return self.downloaded_images
        
        # Step 2: Extract categories using simple ng parameter approach
        self.gallery_categories = await self.extract_gallery_categories_simple(gallery_url)
        
        if not self.gallery_categories:
            print("⚠️  No categories found, falling back to basic crawling")
            internal_links, _ = await self.crawl_page_thoroughly(gallery_url)
            return self.downloaded_images
        
        # Step 3: Limit to requested number of categories or use all if None
        if max_categories == "all":
            categories_to_process = self.gallery_categories
        else:
            categories_to_process = self.gallery_categories[:max_categories]
            
        print(f"📋 Selected {len(categories_to_process)} categories to process:")
        for i, cat in enumerate(categories_to_process):
            print(f"   {i+1}. {cat['name']} (ID: {cat['value']})")
        
        # Step 4: Crawl each category completely using BFS
        categories_processed = 0
        for category in categories_to_process:
            print(f"\n🎨 Starting category: {category['name']}")
            await self.crawl_category_completely(category)
            categories_processed += 1
            
            # Brief pause between categories
            await asyncio.sleep(config.REQUEST_DELAY * 2)
        
        new_images_this_session = len(self.downloaded_images) - initial_image_count
        print(f"\n🎉 Crawl completed!")
        print(f"Categories processed: {categories_processed}")
        print(f"New images downloaded: {new_images_this_session}")
        print(f"Total images in collection: {len(self.downloaded_images)}")
        
        if self.categories_found:
            print(f"📁 Categories found: {', '.join(sorted(self.categories_found))}")
        
        # Final save with run-specific metadata file
        await save_metadata(self.downloaded_images, self.metadata_file)
        print(f"💾 Metadata saved to: {self.metadata_file}")
        
        return self.downloaded_images

    async def get_summary(self) -> Dict:
        """Get comprehensive summary of the crawling session"""
        total_size_bytes = sum(img.get('file_size', 0) for img in self.downloaded_images)
        
        # Count images by category
        category_breakdown = {}
        images_with_descriptions = 0
        
        for img in self.downloaded_images:
            category = img.get('category', 'miscellaneous')
            category_breakdown[category] = category_breakdown.get(category, 0) + 1
            
            if img.get('description'):
                images_with_descriptions += 1
        
        # Get recent images by category (last 3 per category)
        recent_images_by_category = {}
        for img in reversed(self.downloaded_images[-20:]):  # Look at last 20 images
            category = img.get('category', 'miscellaneous')
            if category not in recent_images_by_category:
                recent_images_by_category[category] = []
            if len(recent_images_by_category[category]) < 3:
                recent_images_by_category[category].append(img.get('filename', 'unknown'))
        
        return {
            'total_images': len(self.downloaded_images),
            'pages_visited': len(self.visited_urls),
            'total_size': total_size_bytes / (1024 * 1024),  # MB
            'categories_detected': len(self.gallery_categories) if self.gallery_categories else 0,
            'categories_found': len(self.categories_found),
            'images_with_descriptions': images_with_descriptions,
            'run_directory': self.run_dir,
            'category_breakdown': category_breakdown,
            'recent_images_by_category': recent_images_by_category
        } 