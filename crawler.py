"""
Main crawler for Odexpo Gallery Scraper
"""

import asyncio
import aiohttp
from typing import List, Dict, Set
from urllib.parse import urljoin, urlparse
import time

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from utils.helpers import (
    is_allowed_domain, download_image, save_metadata, 
    load_metadata, create_directory_structure
)
import config

class OdexpoGalleryCrawler:
    """
    Simple crawler for extracting images from Odexpo gallery website
    """
    
    def __init__(self):
        self.visited_urls: Set[str] = set()
        self.downloaded_images: List[Dict] = []
        self.session: aiohttp.ClientSession = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        # Create HTTP session with basic configuration
        connector = aiohttp.TCPConnector(limit=config.MAX_CONCURRENT_REQUESTS)
        timeout = aiohttp.ClientTimeout(total=config.TIMEOUT)
        self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def crawl_page(self, url: str) -> List[Dict]:
        """
        Crawl a single page and extract images with metadata
        """
        if url in self.visited_urls:
            print(f"Already visited: {url}")
            return []
            
        if not is_allowed_domain(url):
            print(f"URL not in allowed domain: {url}")
            return []
            
        print(f"Crawling page: {url}")
        self.visited_urls.add(url)
        
        # Configure crawl4ai
        browser_config = BrowserConfig(
            headless=True,
            verbose=False
        )
        
        run_config = CrawlerRunConfig(
            # Wait for images to load
            wait_for_images=True,
            
            # Exclude external content to focus on allowed domain
            exclude_external_links=True,
            exclude_external_images=True,
            
            # Process content thoroughly
            process_iframes=True,
            remove_overlay_elements=True,
            
            # Cache settings
            cache_mode=CacheMode.BYPASS,
            
            # Basic content filtering
            word_count_threshold=5,
            
            verbose=True
        )
        
        page_images = []
        
        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)
                
                if result.success:
                    print(f"✅ Successfully crawled: {url}")
                    print(f"Page title: {result.metadata.get('title', 'No title')}")
                    
                    # Extract images
                    images = result.media.get("images", [])
                    print(f"Found {len(images)} images on this page")
                    
                    # Process each image
                    for i, img_info in enumerate(images):
                        print(f"Processing image {i+1}/{len(images)}")
                        
                        # Add page context to image metadata
                        enhanced_img_info = {
                            **img_info,
                            'source_page': url,
                            'page_title': result.metadata.get('title', ''),
                            'found_at': time.time()
                        }
                        
                        # Download image
                        downloaded_metadata = await download_image(
                            self.session, enhanced_img_info, url
                        )
                        
                        if downloaded_metadata:
                            page_images.append(downloaded_metadata)
                            self.downloaded_images.append(downloaded_metadata)
                        
                        # Basic throttling
                        await asyncio.sleep(config.REQUEST_DELAY)
                    
                    # Extract internal links for further crawling
                    internal_links = result.links.get("internal", [])
                    print(f"Found {len(internal_links)} internal links")
                    
                    return internal_links
                    
                else:
                    print(f"❌ Failed to crawl {url}: {result.error_message}")
                    
        except Exception as e:
            print(f"Error crawling {url}: {e}")
            
        return []
    
    async def crawl_website(self, start_url: str = None, max_pages: int = 50) -> List[Dict]:
        """
        Crawl the entire website starting from the given URL
        """
        if not start_url:
            start_url = config.BASE_URL
            
        print(f"Starting website crawl from: {start_url}")
        print(f"Allowed domain: {config.ALLOWED_DOMAIN}")
        print(f"Max pages to crawl: {max_pages}")
        
        urls_to_visit = [start_url]
        pages_crawled = 0
        
        while urls_to_visit and pages_crawled < max_pages:
            current_url = urls_to_visit.pop(0)
            
            # Skip if already visited
            if current_url in self.visited_urls:
                continue
                
            # Crawl the page
            new_links = await self.crawl_page(current_url)
            pages_crawled += 1
            
            # Add new internal links to the queue
            for link in new_links:
                link_url = link.get('href', '')
                if link_url and link_url not in self.visited_urls:
                    # Convert relative URLs to absolute
                    if link_url.startswith('/'):
                        link_url = urljoin(current_url, link_url)
                    
                    if is_allowed_domain(link_url) and link_url not in urls_to_visit:
                        urls_to_visit.append(link_url)
            
            print(f"Progress: {pages_crawled}/{max_pages} pages, {len(self.downloaded_images)} images downloaded")
            
            # Basic throttling between pages
            await asyncio.sleep(config.REQUEST_DELAY)
        
        print(f"Crawl completed! Visited {pages_crawled} pages, downloaded {len(self.downloaded_images)} images")
        
        # Save metadata
        await save_metadata(self.downloaded_images)
        
        return self.downloaded_images
    
    async def get_summary(self) -> Dict:
        """Get a summary of the crawl results"""
        return {
            'total_images': len(self.downloaded_images),
            'pages_visited': len(self.visited_urls),
            'total_size_bytes': sum(img.get('size_bytes', 0) for img in self.downloaded_images),
            'images_with_alt_text': len([img for img in self.downloaded_images if img.get('alt_text')]),
            'images_with_title': len([img for img in self.downloaded_images if img.get('title')]),
            'images_with_description': len([img for img in self.downloaded_images if img.get('description')])
        } 