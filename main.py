"""
Main script for Odexpo Gallery Scraper
"""

import asyncio
import sys
from crawler import OdexpoGalleryCrawler
import config

async def main():
    """Main function to run the gallery scraper"""
    print("🎨 Odexpo Gallery Scraper")
    print("=" * 50)
    print(f"Target website: {config.BASE_URL}")
    print(f"Allowed domain: {config.ALLOWED_DOMAIN}")
    print("=" * 50)
    
    try:
        # Create and run the crawler
        async with OdexpoGalleryCrawler() as crawler:
            # Crawl the website (limit to 10 pages for testing)
            images = await crawler.crawl_website(max_pages=10)
            
            # Get summary
            summary = await crawler.get_summary()
            
            # Display results
            print("\n" + "=" * 50)
            print("📊 CRAWL SUMMARY")
            print("=" * 50)
            print(f"Total images downloaded: {summary['total_images']}")
            print(f"Pages visited: {summary['pages_visited']}")
            print(f"Total size: {summary['total_size_bytes'] / (1024*1024):.2f} MB")
            print(f"Images with alt text: {summary['images_with_alt_text']}")
            print(f"Images with title: {summary['images_with_title']}")
            print(f"Images with description: {summary['images_with_description']}")
            
            if images:
                print(f"\n📂 Images saved to: {config.IMAGES_DIR}")
                print(f"📄 Metadata saved to: {config.METADATA_FILE}")
                
                # Show some example images
                print("\n🖼️  Example downloaded images:")
                for i, img in enumerate(images[:5]):
                    print(f"  {i+1}. {img['filename']} - {img['alt_text'][:50]}..." if img['alt_text'] else f"  {i+1}. {img['filename']}")
            
    except KeyboardInterrupt:
        print("\n⏹️  Crawling interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during crawling: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
