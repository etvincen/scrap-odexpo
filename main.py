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
            print(f"Total images in collection: {summary['total_images']}")
            print(f"Pages visited this session: {summary['pages_visited']}")
            print(f"Total size: {summary['total_size_bytes'] / (1024*1024):.2f} MB")
            print(f"Images with alt text: {summary['images_with_alt_text']}")
            print(f"Images with title: {summary['images_with_title']}")
            print(f"Images with description: {summary['images_with_description']}")
            print(f"Unique categories found: {summary['unique_categories']}")
            
            # Show categories and their counts
            if summary['categories']:
                print(f"\n📁 CATEGORIES BREAKDOWN:")
                for category, count in sorted(summary['categories'].items()):
                    print(f"  {category}: {count} images")
                
            if images:
                print(f"\n📂 Images organized in: {config.IMAGES_DIR}")
                print(f"📄 Metadata saved to: {config.METADATA_FILE}")
                
                # Show some example images from different categories
                print("\n🖼️  Recent downloaded images by category:")
                shown_categories = set()
                for img in reversed(images[-10:]):  # Show last 10 images
                    category = img.get('category', 'miscellaneous')
                    if category not in shown_categories:
                        print(f"  [{category}] {img['filename']}")
                        shown_categories.add(category)
                        if len(shown_categories) >= 5:  # Limit to 5 categories shown
                            break
            
    except KeyboardInterrupt:
        print("\n⏹️  Crawling interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during crawling: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
