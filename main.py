"""
Unified Odexpo Gallery Tool
Comprehensive script with multiple operations: crawling, organizing, and renaming
"""

import asyncio
import sys
import config
from crawler import PlaywrightOdexpoGalleryCrawler
from rename_files import find_all_metadata_files, rename_files_in_metadata

async def show_menu():
    """Display the main menu options"""
    print("🎨 Odexpo Gallery Tool - Unified Interface")
    print("=" * 60)
    print("Choose an operation:")
    print()
    print("1. 🕷️  Advanced Crawling - Download new images from gallery")
    print("4. 📊 Show Statistics - Display collection overview")
    print("5. ❌ Exit")
    print()
    print("=" * 60)

async def crawl_gallery():
    """Advanced crawling with Playwright"""
    print("\n🕷️  Starting Advanced Gallery Crawling")
    print("=" * 50)
    
    # Ask for number of categories
    try:
        max_cats = input("How many categories to process? (default: all): ").strip()
        if not max_cats or max_cats.lower() == "all":
            max_categories = "all"
            categories_display = "all"
        else:
            max_categories = int(max_cats)
            categories_display = str(max_categories)
    except ValueError:
        print("⚠️  Invalid input, defaulting to all categories")
        max_categories = "all"
        categories_display = "all"
    
    print(f"Will process {categories_display} categories")
    print(f"Target website: {config.BASE_URL}")
    print(f"Strategy: Direct Playwright → DOM extraction → Category separation")
    print()
    
    async with PlaywrightOdexpoGalleryCrawler(use_timestamped_run=True) as crawler:
        print(f"📁 Crawl run directory: {crawler.run_dir}")
        
        # Start crawling
        downloaded_images = await crawler.crawl_website_advanced(
            start_url=config.BASE_URL,
            max_categories=max_categories
        )
        
        # Get and display summary
        summary = await crawler.get_summary()
        
        print()
        print("=" * 50)
        print("📊 CRAWL SUMMARY")
        print("=" * 50)
        print(f"Total images: {summary['total_images']}")
        print(f"Pages visited: {summary['pages_visited']}")
        print(f"Total size: {summary['total_size']:.2f} MB")
        print(f"Categories found: {summary['categories_found']}")
        print(f"Run directory: {summary['run_directory']}")
        
        if summary['category_breakdown']:
            print(f"\n📁 Categories:")
            for category, count in summary['category_breakdown'].items():
                print(f"  {category}: {count} images")


async def rename_files_interactive():
    """Interactive file renaming with title + last 3 digits"""
    print("\n🏷️  File Renaming Tool")
    print("=" * 50)
    print("This will:")
    print("✅ Rename files to: [cleaned_title]_[last3digits].jpg")
    print("✅ Clean categories (lowercase, no accents, no underscores)")
    print("✅ Update all metadata files")
    print("✅ Move files to cleaned category folders")
    print()
    
    # Find metadata files
    metadata_files = await find_all_metadata_files()
    
    if not metadata_files:
        print("❌ No metadata files found!")
        return
    
    print(f"📂 Found {len(metadata_files)} metadata files:")
    for i, file in enumerate(metadata_files, 1):
        print(f"   {i}. {file}")
    
    print()
    
    # Ask for dry run first
    dry_run_response = input("Run in DRY RUN mode first? (Y/n): ").strip().lower()
    dry_run = dry_run_response != 'n'
    
    if dry_run:
        print("\n🔍 DRY RUN MODE - No files will be changed")
    else:
        print("\n🚀 LIVE MODE - Files will be renamed!")
        confirm = input("Are you sure? Type 'yes' to proceed: ").strip().lower()
        if confirm != 'yes':
            print("❌ Operation cancelled")
            return
    
    # Process each metadata file
    total_stats = {"processed": 0, "renamed": 0, "errors": 0, "categories_updated": 0}
    
    for metadata_file in metadata_files:
        stats = await rename_files_in_metadata(metadata_file, dry_run)
        total_stats["processed"] += stats["processed"]
        total_stats["renamed"] += stats["renamed"]
        total_stats["errors"] += stats["errors"]
        total_stats["categories_updated"] += stats.get("categories_updated", 0)
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 RENAME SUMMARY")
    print("=" * 50)
    print(f"Files processed: {total_stats['processed']}")
    print(f"Files renamed: {total_stats['renamed']}")
    print(f"Categories cleaned: {total_stats['categories_updated']}")
    print(f"Errors: {total_stats['errors']}")
    
    if dry_run and total_stats['renamed'] > 0:
        print(f"\n💡 To apply changes, run this option again and choose 'n' for dry run")
    elif not dry_run:
        print(f"\n✅ File renaming completed successfully!")

async def show_statistics():
    """Show collection statistics"""
    print("\n📊 Collection Statistics")
    print("=" * 50)
    
    metadata_files = await find_all_metadata_files()
    
    if not metadata_files:
        print("❌ No metadata files found!")
        return
    
    total_images = 0
    total_size = 0
    all_categories = {}
    
    for metadata_file in metadata_files:
        try:
            from utils.helpers import load_metadata
            metadata = await load_metadata(metadata_file)
            
            if metadata:
                file_count = len(metadata)
                total_images += file_count
                
                # Calculate size and categories for this file
                file_size = sum(img.get('file_size', 0) for img in metadata) / (1024 * 1024)
                total_size += file_size
                
                # Count categories
                for img in metadata:
                    category = img.get('category', 'miscellaneous')
                    all_categories[category] = all_categories.get(category, 0) + 1
                
                print(f"📁 {metadata_file}")
                print(f"   Images: {file_count}")
                print(f"   Size: {file_size:.2f} MB")
                
        except Exception as e:
            print(f"❌ Error reading {metadata_file}: {e}")
    
    print(f"\n📊 TOTAL COLLECTION")
    print(f"   Total images: {total_images}")
    print(f"   Total size: {total_size:.2f} MB")
    print(f"   Categories: {len(all_categories)}")
    
    if all_categories:
        print(f"\n📁 CATEGORY BREAKDOWN:")
        for category, count in sorted(all_categories.items()):
            print(f"   {category}: {count} images")

async def main():
    """Main unified interface"""
    while True:
        await show_menu()
        
        try:
            choice = input("Enter your choice (1-5): ").strip()
            
            if choice == '1':
                await crawl_gallery()
            elif choice == '2':
                await show_statistics()
            elif choice == '3':
                print("\n👋 Goodbye!")
                sys.exit(0)
            else:
                print("\n❌ Invalid choice. Please enter 1-3.")
                
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ Error: {e}")
        
        # Pause before showing menu again
        input("\nPress Enter to continue...")
        print("\n" * 2)

if __name__ == "__main__":
    asyncio.run(main()) 