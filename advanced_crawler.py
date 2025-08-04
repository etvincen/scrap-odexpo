"""
Advanced crawler for Odexpo Gallery Scraper with BFS and category-aware crawling
"""

import asyncio
import json
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, parse_qs, urlencode

import aiohttp
from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

import config
from utils.helpers import (
    is_allowed_domain, 
    download_image, 
    save_metadata, 
    load_metadata,
    get_downloaded_urls_from_metadata
)

class AdvancedOdexpoGalleryCrawler:
    """
    Advanced crawler with BFS strategy and category-aware crawling
    """
    
    def __init__(self, use_timestamped_run: bool = True):
        self.visited_urls: Set[str] = set()
        self.downloaded_images: List[Dict] = []
        self.downloaded_urls: Set[str] = set()
        self.session: aiohttp.ClientSession = None
        self.categories_found: Set[str] = set()
        
        # Advanced crawling state
        self.gallery_categories: List[Dict] = []
        self.category_queues: Dict[str, deque] = defaultdict(deque)
        self.current_category: Optional[str] = None
        
        # Timestamped run directory
        if use_timestamped_run:
            self.run_dir = config.get_timestamped_run_dir()
            self.images_dir = f"{self.run_dir}/images"
            self.metadata_file = f"{self.run_dir}/metadata.json"
        else:
            self.run_dir = config.ASSETS_DIR
            self.images_dir = config.IMAGES_DIR
            self.metadata_file = config.METADATA_FILE
            
        # Create run directory
        Path(self.run_dir).mkdir(parents=True, exist_ok=True)
        
    async def __aenter__(self):
        """Async context manager entry"""
        # Create HTTP session with basic configuration
        connector = aiohttp.TCPConnector(limit=config.MAX_CONCURRENT_REQUESTS)
        timeout = aiohttp.ClientTimeout(total=config.TIMEOUT)
        self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        
        # Load existing metadata to avoid downloading duplicates
        existing_metadata = await load_metadata(self.metadata_file)
        self.downloaded_urls = get_downloaded_urls_from_metadata(existing_metadata)
        self.downloaded_images = existing_metadata
        
        if self.downloaded_urls:
            print(f"📂 Loaded {len(self.downloaded_urls)} previously downloaded images")
            
        print(f"📁 Crawl run directory: {self.run_dir}")
        
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def extract_gallery_categories(self, url: str) -> List[Dict]:
        """DEPRECATED: Old complex method - use extract_gallery_categories_simple instead"""
        return await self.extract_gallery_categories_simple(url)
    
    def _build_category_url(self, base_url: str, category_value: str) -> str:
        """Build URL for a specific gallery category"""
        try:
            # Handle different value formats
            if category_value.startswith('default.asp'):
                # Value is already a relative URL path
                if 'galerie=' in category_value:
                    # Extract the galerie parameter for clean URL building
                    import re
                    galerie_match = re.search(r'galerie=([^&]+)', category_value)
                    if galerie_match:
                        galerie_id = galerie_match.group(1)
                        return f"{config.BASE_URL}/default.asp?galerie={galerie_id}&lg=&page=10076&sm="
                    else:
                        # Use the value as-is, just ensure it's absolute
                        return urljoin(config.BASE_URL, category_value)
                else:
                    return urljoin(config.BASE_URL, category_value)
            else:
                # Value is likely a galerie ID
                return f"{config.BASE_URL}/default.asp?galerie={category_value}&lg=&page=10076&sm="
                
        except Exception as e:
            print(f"⚠️  Error building category URL for {category_value}: {e}")
            # Fallback: treat as galerie ID
            return f"{config.BASE_URL}/default.asp?galerie={category_value}&lg=&page=10076&sm="
    
    def _extract_category_from_url(self, url: str) -> Optional[str]:
        """Extract category name from URL parameters"""
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        # Look for gallery category in various parameters
        for param in ['ng', 'galerie']:
            if param in query_params:
                return query_params[param][0]
        
        return None
    
    def _get_pagination_urls(self, url: str, links: List[Dict]) -> List[str]:
        """Extract pagination URLs for the current category"""
        pagination_urls = []
        current_category = self._extract_category_from_url(url)
        
        if not current_category:
            return pagination_urls
        
        for link in links:
            link_url = link.get('href', '')
            if not link_url:
                continue
                
            # Convert to absolute URL
            if link_url.startswith('/'):
                link_url = urljoin(url, link_url)
                
            # Check if this is a pagination link for the same category
            link_category = self._extract_category_from_url(link_url)
            if link_category == current_category:
                # Check for numbered pagination (1, 2, 3, etc.)
                link_text = link.get('text', '').strip()
                
                # Look for numbered pagination or pagination patterns in URL
                is_pagination = (
                    link_text.isdigit() or  # Direct number links like "1", "2", "3"
                    any(keyword in link_text for keyword in config.PAGINATION_KEYWORDS) or
                    any(pattern in link_url for pattern in config.CATEGORY_URL_PATTERNS) or
                    'page=' in link_url.lower()
                )
                
                if is_pagination:
                    pagination_urls.append(link_url)
                    print(f"    Found pagination: {link_text} -> {link_url}")
        
        return pagination_urls
    
    async def crawl_page_thoroughly(self, url: str) -> Tuple[List[Dict], List[str]]:
        """
        Crawl a single page thoroughly, ensuring all images are processed
        Returns: (internal_links, pagination_links)
        """
        if url in self.visited_urls:
            print(f"Already visited: {url}")
            return [], []
            
        if not is_allowed_domain(url):
            print(f"URL not in allowed domain: {url}")
            return [], []
            
        print(f"🔍 Crawling page thoroughly: {url}")
        self.visited_urls.add(url)
        
        # DIAGNOSTIC: Add more logging for page type analysis
        print(f"🔬 DIAGNOSTIC: Starting thorough crawl of {url}")
        
        # Configure crawl4ai with more patience for images
        browser_config = BrowserConfig(
            headless=True,
            verbose=False
        )
        
        run_config = CrawlerRunConfig(
            # Enhanced image loading settings
            wait_for_images=True,
            scan_full_page=True,  # Ensure we scroll to load all images
            scroll_delay=3.0,     # INCREASED: Wait longer between scrolls for lazy loading
            
            # Exclude external content to focus on allowed domain
            exclude_external_links=True,
            exclude_external_images=False,  # CHANGED: Allow external images in case some are hosted elsewhere
            
            # Process content thoroughly
            process_iframes=True,
            remove_overlay_elements=True,
            
            # Enhanced waiting and loading
            page_timeout=60000,   # Increase page timeout to 60 seconds
            delay_before_return_html=2.0,  # Wait 2 seconds before returning HTML
            
            # Cache settings
            cache_mode=CacheMode.BYPASS,
            
            # Content filtering - be more permissive
            word_count_threshold=1,  # Reduced threshold
            image_description_min_word_threshold=1,  # Allow shorter descriptions
            
            # Enhanced media extraction
            screenshot=False,  # Don't take screenshots to save time
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            
            verbose=True
        )
        
        new_images_count = 0
        internal_links = []
        pagination_links = []
        
        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)
                
                if result.success:
                    print(f"✅ Successfully crawled: {url}")
                    print(f"Page title: {result.metadata.get('title', 'No title')}")
                    
                    # DIAGNOSTIC: Analyze page content
                    print(f"🔬 DIAGNOSTIC: Page analysis:")
                    print(f"   - HTML length: {len(result.html) if result.html else 0} chars")
                    print(f"   - Cleaned HTML length: {len(result.cleaned_html) if result.cleaned_html else 0} chars")
                    print(f"   - Markdown length: {len(result.markdown) if result.markdown else 0} chars")
                    
                    # DIAGNOSTIC: Check for gallery indicators in content
                    html_lower = result.html.lower() if result.html else ""
                    gallery_indicators = {
                        'select_dropdown': 'form-control-comb' in html_lower,
                        'gallery_images': 'galerie=' in html_lower,
                        'image_thumbnails': 'thumbnail' in html_lower or 'thumb' in html_lower,
                        'image_grid': 'grid' in html_lower,
                        'lazy_loading': 'lazy' in html_lower or 'data-src' in html_lower,
                        'javascript_gallery': 'onclick' in html_lower and 'image' in html_lower
                    }
                    print(f"🔬 DIAGNOSTIC: Gallery indicators found:")
                    for indicator, found in gallery_indicators.items():
                        print(f"   - {indicator}: {found}")
                    
                    # Extract images with detailed logging
                    images = result.media.get("images", [])
                    print(f"🔬 DIAGNOSTIC: crawl4ai extracted {len(images)} images")
                    
                    # DIAGNOSTIC: Check for potential image extraction issues
                    if len(images) < 10:  # Suspicious if gallery page has < 10 images
                        print(f"🔬 SUSPICIOUS: Only {len(images)} images found - investigating...")
                        
                        # Check HTML for all img tags
                        if result.html:
                            import re
                            all_img_tags = re.findall(r'<img[^>]*>', result.html, re.IGNORECASE)
                            print(f"🔬 HTML Analysis: Found {len(all_img_tags)} total <img> tags in HTML")
                            
                            # Look for gallery-specific image patterns
                            gallery_img_patterns = [
                                r'<img[^>]*src=["\']images/\d+/[^"\']*["\'][^>]*>',  # images/ID/filename pattern
                                r'<img[^>]*src=["\'][^"\']*\.jpg["\'][^>]*>',         # Any .jpg
                                r'<img[^>]*src=["\'][^"\']*\.png["\'][^>]*>',         # Any .png
                            ]
                            
                            for i, pattern in enumerate(gallery_img_patterns):
                                matches = re.findall(pattern, result.html, re.IGNORECASE)
                                print(f"   Pattern {i+1} (gallery images): {len(matches)} matches")
                                if matches and len(matches) > len(images):
                                    print(f"   🚨 DISCREPANCY: HTML has {len(matches)} gallery images but crawl4ai only extracted {len(images)}")
                                    # Show first few examples
                                    for j, match in enumerate(matches[:3]):
                                        print(f"      Example {j+1}: {match[:100]}...")
                    
                    # DIAGNOSTIC: Analyze crawl4ai's image filtering
                    if hasattr(result, 'media') and 'images' in result.media:
                        all_media_images = result.media.get("images", [])
                        print(f"🔬 crawl4ai Media Analysis:")
                        print(f"   - Total images in media: {len(all_media_images)}")
                        
                        # Check if images were filtered by score
                        low_score_images = [img for img in all_media_images if img.get('score', 0) < 3]
                        high_score_images = [img for img in all_media_images if img.get('score', 0) >= 3]
                        print(f"   - High score images (≥3): {len(high_score_images)}")
                        print(f"   - Low score images (<3): {len(low_score_images)}")
                        
                        # Check image sizes
                        if all_media_images:
                            has_dimensions = [img for img in all_media_images if img.get('width') and img.get('height')]
                            print(f"   - Images with dimensions: {len(has_dimensions)}")
                            
                            # Show size distribution for first few
                            for i, img in enumerate(all_media_images[:5]):
                                src = img.get('src', 'NO_SRC')[:50]
                                score = img.get('score', 'NO_SCORE')
                                width = img.get('width', 'NO_WIDTH')
                                height = img.get('height', 'NO_HEIGHT')
                                print(f"      Image {i+1}: score={score}, size={width}x{height}, src={src}...")
                    
                    # DIAGNOSTIC: Analyze each extracted image
                    if images:
                        print(f"🔬 DIAGNOSTIC: Image analysis:")
                        for i, img in enumerate(images[:5]):  # Show first 5 for analysis
                            src = img.get('src', 'NO_SRC')
                            alt = img.get('alt', 'NO_ALT')
                            score = img.get('score', 'NO_SCORE')
                            desc = img.get('desc', 'NO_DESC')[:50] + '...' if img.get('desc') else 'NO_DESC'
                            print(f"   Image {i+1}: src={src}, alt={alt}, score={score}")
                            print(f"              desc={desc}")
                    
                    # DIAGNOSTIC: Check for potential image sources in HTML
                    if result.html:
                        import re
                        # Look for various image patterns
                        img_patterns = [
                            r'<img[^>]*src=["\']([^"\']*)["\']',
                            r'data-src=["\']([^"\']*)["\']',
                            r'background-image:\s*url\(["\']?([^"\']*)["\']?\)',
                        ]
                        
                        all_potential_images = set()
                        for pattern in img_patterns:
                            matches = re.findall(pattern, result.html, re.IGNORECASE)
                            all_potential_images.update(matches)
                        
                        # Filter for actual images
                        image_urls = [url for url in all_potential_images 
                                    if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp'])]
                        
                        print(f"🔬 DIAGNOSTIC: HTML regex found {len(image_urls)} potential image URLs")
                        if image_urls:
                            print(f"   First 3 URLs: {image_urls[:3]}")
                    
                    print(f"Found {len(images)} images on this page")
                    
                    # Process each image synchronously to ensure completion
                    for i, img_info in enumerate(images):
                        print(f"Processing image {i+1}/{len(images)}")
                        
                        # DIAGNOSTIC: Log image processing details
                        img_src = img_info.get('src', '')
                        print(f"🔬 DIAGNOSTIC: Processing image src: {img_src}")
                        
                        # Add page context to image metadata
                        enhanced_img_info = {
                            **img_info,
                            'source_page': url,
                            'page_title': result.metadata.get('title', ''),
                            'found_at': time.time(),
                            'crawl_run': self.run_dir
                        }
                        
                        # Download image (with duplicate checking)
                        downloaded_metadata = await download_image(
                            self.session, enhanced_img_info, url, self.downloaded_urls, self.images_dir
                        )
                        
                        if downloaded_metadata:
                            self.downloaded_images.append(downloaded_metadata)
                            new_images_count += 1
                            
                            # Track categories found
                            category = downloaded_metadata.get('category', 'miscellaneous')
                            self.categories_found.add(category)
                            print(f"🔬 DIAGNOSTIC: Successfully downloaded to category: {category}")
                        else:
                            print(f"🔬 DIAGNOSTIC: Failed to download image: {img_src}")
                        
                        # Throttling between images
                        await asyncio.sleep(config.REQUEST_DELAY)
                    
                    print(f"📥 Downloaded {new_images_count} new images from this page")
                    print(f"🔬 DIAGNOSTIC: Expected vs Actual - Expected: multiple images, Got: {new_images_count}")
                    
                    # Extract all links
                    all_links = result.links.get("internal", [])
                    print(f"Found {len(all_links)} internal links")
                    
                    # DIAGNOSTIC: Analyze link types
                    if all_links:
                        gallery_links = [link for link in all_links if 'galerie=' in link.get('href', '')]
                        page_links = [link for link in all_links if 'page=' in link.get('href', '')]
                        print(f"🔬 DIAGNOSTIC: Link analysis:")
                        print(f"   - Gallery links: {len(gallery_links)}")
                        print(f"   - Page links: {len(page_links)}")
                        if gallery_links:
                            print(f"   - Sample gallery link: {gallery_links[0].get('href', '')}")
                    
                    # Separate pagination links from other internal links
                    pagination_links = self._get_pagination_urls(url, all_links)
                    internal_links = [link for link in all_links if link.get('href') not in pagination_links]
                    
                    print(f"  - {len(pagination_links)} pagination links")
                    print(f"  - {len(internal_links)} other internal links")
                    
                else:
                    print(f"❌ Failed to crawl {url}: {result.error_message}")
                    
        except Exception as e:
            print(f"Error crawling {url}: {e}")
            import traceback
            print(f"🔬 DIAGNOSTIC: Full error traceback:")
            traceback.print_exc()
            
        return internal_links, pagination_links

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

    async def discover_gallery_page(self, start_url: str) -> Optional[str]:
        """Find the gallery page by looking for the "galeries" navigation link"""
        print(f"🔍 Looking for gallery page from: {start_url}")
        
        browser_config = BrowserConfig(headless=True, verbose=False)
        run_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, verbose=True)
        
        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=start_url, config=run_config)
                
                if result.success:
                    internal_links = result.links.get("internal", [])
                    
                    # Look specifically for the "galeries" link
                    for link in internal_links:
                        link_text = link.get('text', '').lower()
                        link_url = link.get('href', '')
                        
                        if 'galerie' in link_text and 'page=10076' in link_url:
                            gallery_url = urljoin(start_url, link_url) if link_url.startswith('/') else link_url
                            print(f"🎯 Found gallery page: {gallery_url}")
                            return gallery_url
                    
                    print("⚠️  Gallery page not found in navigation")
                    return None
                else:
                    print(f"❌ Failed to crawl homepage: {result.error_message}")
                    return None
                    
        except Exception as e:
            print(f"❌ Error during gallery discovery: {e}")
            return None

    async def extract_gallery_categories_simple(self, gallery_url: str) -> List[Dict]:
        """Extract gallery categories directly from gallery page links using ng parameter"""
        print(f"🔍 Extracting categories from gallery page: {gallery_url}")
        
        browser_config = BrowserConfig(headless=True, verbose=False)
        run_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, verbose=True)
        
        categories = []
        
        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=gallery_url, config=run_config)
                
                if result.success:
                    internal_links = result.links.get("internal", [])
                    print(f"Found {len(internal_links)} internal links")
                    
                    # Find all gallery category links
                    for link in internal_links:
                        link_url = link.get('href', '')
                        link_text = link.get('text', '').strip()
                        
                        # Look for gallery category links (contain galerie= parameter)
                        if 'galerie=' in link_url and 'ng=' in link_url:
                            # Make absolute URL
                            if link_url.startswith('/'):
                                full_url = urljoin(gallery_url, link_url)
                            else:
                                full_url = link_url
                            
                            # Extract category info from URL
                            parsed = urlparse(full_url)
                            query_params = parse_qs(parsed.query)
                            
                            galerie_id = query_params.get('galerie', [''])[0]
                            ng_value = query_params.get('ng', [''])[0]
                            
                            if galerie_id and ng_value:
                                # Clean up the ng value (URL decode and clean)
                                import urllib.parse
                                category_name = urllib.parse.unquote_plus(ng_value).strip()
                                
                                categories.append({
                                    'name': category_name,
                                    'value': galerie_id,
                                    'url': full_url,
                                    'link_text': link_text
                                })
                                
                                print(f"   Found category: {category_name} (ID: {galerie_id})")
                    
                    # Remove duplicates based on galerie_id
                    unique_categories = []
                    seen_ids = set()
                    for cat in categories:
                        if cat['value'] not in seen_ids:
                            unique_categories.append(cat)
                            seen_ids.add(cat['value'])
                    
                    print(f"✅ Found {len(unique_categories)} unique gallery categories")
                    return unique_categories
                    
                else:
                    print(f"❌ Failed to crawl gallery page: {result.error_message}")
                    return []
                    
        except Exception as e:
            print(f"❌ Error extracting categories: {e}")
            return []

    def _test_page_for_working_select(self, html: str, url: str) -> bool:
        """DEPRECATED: No longer needed with simplified ng parameter approach"""
        return False

    async def crawl_website_advanced(self, start_url: str = None, max_categories: int = 3) -> List[Dict]:
        """
        Simplified advanced website crawling using direct gallery navigation
        """
        if not start_url:
            start_url = config.BASE_URL
            
        print(f"🚀 Starting advanced website crawl from: {start_url}")
        print(f"Allowed domain: {config.ALLOWED_DOMAIN}")
        print(f"Max categories: {max_categories}")
        print(f"Strategy: Direct gallery navigation + ng parameter extraction")
        
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
        
        # Step 3: Limit to requested number of categories
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