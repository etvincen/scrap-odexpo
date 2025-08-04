"""
Advanced Odexpo Gallery Scraper
Enhanced version with Playwright for direct DOM control
"""

import asyncio
import config
from advanced_crawler import PlaywrightOdexpoGalleryCrawler

async def main():
    print("🎨 Advanced Odexpo Gallery Scraper")
    print("=" * 60)
    print(f"Target website: {config.BASE_URL}")
    print(f"Allowed domain: {config.ALLOWED_DOMAIN}")
    print("Features: Direct Playwright | DOM Control | BFS Crawling")
    print("=" * 60)
    print(f"Max categories to process: 3")
    print(f"Pages per category: UNLIMITED (until exhausted)")
    print("Strategy: Direct Playwright → DOM extraction → Category separation")
    print()
    
    async with PlaywrightOdexpoGalleryCrawler(use_timestamped_run=True) as crawler:
        print(f"📁 Crawl run directory: {crawler.run_dir}")
        
        # Start crawling from homepage - let it discover the gallery intelligently
        downloaded_images = await crawler.crawl_website_advanced(
            start_url=config.BASE_URL,  # Start from homepage
            max_categories=3
        )
        
        # Get and display summary
        summary = await crawler.get_summary()
        
        print()
        print("=" * 60)
        print("📊 ADVANCED CRAWL SUMMARY")
        print("=" * 60)
        print(f"Total images in collection: {summary['total_images']}")
        print(f"Pages visited this session: {summary['pages_visited']}")
        print(f"Total size: {summary['total_size']:.2f} MB")
        print(f"Gallery categories detected: {summary['categories_detected']}")
        print(f"Image categories found: {summary['categories_found']}")
        print(f"Images with descriptions: {summary['images_with_descriptions']}")
        print(f"Run directory: {summary['run_directory']}")
        print()
        
        if summary['category_breakdown']:
            print("📁 IMAGE CATEGORIES BREAKDOWN:")
            for category, count in summary['category_breakdown'].items():
                print(f"  {category}: {count} images")
            print()
        
        print(f"📂 Images organized in: {crawler.images_dir}")
        print(f"📄 Metadata saved to: {crawler.metadata_file}")
        print()
        
        if summary['recent_images_by_category']:
            print("🖼️  Recent images by category:")
            for category, images in summary['recent_images_by_category'].items():
                recent_files = ', '.join(images[:3])  # Show first 3
                print(f"  [{category}] {recent_files}")
        
        print()
        print("✅ Advanced crawl completed successfully!")
        print("🔍 BFS strategy ensured complete category coverage")
        print("📅 Timestamped run preserves crawl history")
        print("🎯 Direct Playwright DOM extraction (no image filtering!)")
        print()

if __name__ == "__main__":
    asyncio.run(main()) 