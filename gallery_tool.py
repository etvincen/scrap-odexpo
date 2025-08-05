#!/usr/bin/env python3
"""
Odexpo Gallery Tool - Simple Direct Launcher
Automatically runs the complete workflow: Crawl → Download → Auto-rename → Organize
"""

import asyncio
import sys
import os
import config
from advanced_crawler import PlaywrightOdexpoGalleryCrawler
from rename_files import find_all_metadata_files, rename_files_in_metadata

async def auto_rename_after_crawl(crawl_run_dir: str):
    """Automatically rename files after a crawl session"""
    print("\n🏷️  Auto-renaming downloaded files...")
    print("=" * 40)
    
    # Find the metadata file for this crawl run
    metadata_file = os.path.join(crawl_run_dir, "metadata.json")
    
    if not os.path.exists(metadata_file):
        print("⚠️  No metadata file found for auto-renaming")
        return
    
    try:
        # Rename files automatically (no dry run)
        stats = await rename_files_in_metadata(metadata_file, dry_run=False)
        
        print(f"\n✅ Auto-rename completed:")
        print(f"   Files processed: {stats['processed']}")
        print(f"   Files renamed: {stats['renamed']}")
        print(f"   Categories cleaned: {stats.get('categories_updated', 0)}")
        print(f"   Errors: {stats['errors']}")
        
    except Exception as e:
        print(f"❌ Error during auto-rename: {e}")

async def crawl_with_auto_rename():
    """Enhanced crawling with automatic file renaming"""
    print("\n🕷️  Starting Gallery Crawl with Auto-Rename")
    print("=" * 50)
    
    # Ask for number of categories with a sensible default
    try:
        max_cats = input("How many painting categories to process? (default: all): ").strip()
        if not max_cats or max_cats.lower() == "all":
            max_categories = "all"  # Pass "all" as string to match the crawler logic
            categories_display = "all"
        else:
            max_categories = int(max_cats)
            categories_display = str(max_categories)
    except ValueError:
        print("⚠️  Invalid input, defaulting to all categories")
        max_categories = "all"  # Pass "all" as string
        categories_display = "all"
    
    print(f"Will process {categories_display} categories")
    print(f"Target website: {config.BASE_URL}")
    print("Workflow: Crawl → Download → Auto-rename → Organize")
    print()
    
    async with PlaywrightOdexpoGalleryCrawler(use_timestamped_run=True) as crawler:
        print(f"📁 Crawl run directory: {crawler.run_dir}")
        
        # Start crawling
        downloaded_images = await crawler.crawl_website_advanced(
            start_url=config.BASE_URL,
            max_categories=max_categories
        )
        
        # Get and display crawl summary
        summary = await crawler.get_summary()
        
        print()
        print("=" * 50)
        print("📊 CRAWL SUMMARY")
        print("=" * 50)
        print(f"Images downloaded: {summary['total_images']}")
        print(f"Pages visited: {summary['pages_visited']}")
        print(f"Total size: {summary['total_size']:.2f} MB")
        print(f"Categories found: {summary['categories_found']}")
        print(f"Run directory: {summary['run_directory']}")
        
        if summary['category_breakdown']:
            print(f"\n📁 Categories found:")
            for category, count in summary['category_breakdown'].items():
                print(f"  {category}: {count} images")
        
        # Auto-rename files if any were downloaded
        if summary['total_images'] > 0:
            await auto_rename_after_crawl(crawler.run_dir)
        else:
            print("\n⚠️  No new images downloaded, skipping auto-rename")

async def main():
    """Simple direct launcher - runs complete workflow automatically"""
    print("🎨 Odexpo Gallery Tool - Direct Launcher")
    print("=" * 50)
    print("This tool automatically runs the complete workflow:")
    print("✅ Crawl gallery pages")
    print("✅ Download high-resolution images") 
    print("✅ Auto-rename files with cleaned titles")
    print("✅ Organize into cleaned category folders")
    print("=" * 50)
    print()
    
    try:
        await crawl_with_auto_rename()
        print("\n🎉 Complete workflow finished successfully!")
        print("Your images are downloaded, renamed, and organized.")
        
    except KeyboardInterrupt:
        print("\n\n👋 Operation cancelled by user!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    # Check if we're in the right directory
    if not os.path.exists("advanced_crawler.py"):
        print("❌ Error: This script must be run from the project root directory")
        print("   Please navigate to the scrap-odexpo directory and try again")
        sys.exit(1)
    
    # Run the direct workflow
    asyncio.run(main()) 