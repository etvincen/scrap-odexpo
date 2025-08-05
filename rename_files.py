"""
Rename downloaded files based on title field + last 3 digits of current filename
Also clean up categories to be lowercase without accents or underscores
"""

import asyncio
import os
import re
import shutil
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional
from utils.helpers import load_metadata, save_metadata
import json

def clean_category(category: str) -> str:
    """
    Clean category to be lowercase without accents or underscores
    """
    if not category:
        return "miscellaneous"
    
    # Convert to lowercase
    cleaned = category.lower()
    
    # Remove accents by normalizing to NFD and removing combining characters
    cleaned = unicodedata.normalize('NFD', cleaned)
    cleaned = ''.join(char for char in cleaned if unicodedata.category(char) != 'Mn')
    
    # Replace underscores and spaces with hyphens
    cleaned = re.sub(r'[_\s]+', '-', cleaned)
    
    # Remove any non-alphanumeric characters except hyphens
    cleaned = re.sub(r'[^a-z0-9-]', '', cleaned)
    
    # Remove multiple consecutive hyphens
    cleaned = re.sub(r'-+', '-', cleaned)
    
    # Remove leading/trailing hyphens
    cleaned = cleaned.strip('-')
    
    # Ensure it's not empty
    if not cleaned:
        return "miscellaneous"
    
    return cleaned

def clean_title_for_filename(title: str) -> str:
    """
    Clean title to make it safe for use as a filename
    """
    if not title:
        return "untitled"
    
    # Convert to lowercase
    cleaned = title.lower()
    
    # Remove accents by normalizing to NFD and removing combining characters
    cleaned = unicodedata.normalize('NFD', cleaned)
    cleaned = ''.join(char for char in cleaned if unicodedata.category(char) != 'Mn')
    
    # Replace spaces and special characters with underscores
    cleaned = re.sub(r'[^a-z0-9]', '_', cleaned)
    
    # Remove multiple consecutive underscores
    cleaned = re.sub(r'_+', '_', cleaned)
    
    # Remove leading/trailing underscores
    cleaned = cleaned.strip('_')
    
    # Limit length to avoid filesystem issues
    cleaned = cleaned[:50]
    
    # Ensure it's not empty
    if not cleaned:
        return "untitled"
    
    return cleaned

def extract_last_three_digits(filename: str) -> str:
    """
    Extract the last 3 digits from the filename before the extension
    """
    # Remove extension
    name_without_ext = os.path.splitext(filename)[0]
    
    # Find all digits in the filename
    digits = re.findall(r'\d', name_without_ext)
    
    # Get the last 3 digits, or pad with zeros if less than 3
    if len(digits) >= 3:
        return ''.join(digits[-3:])
    elif len(digits) > 0:
        return ''.join(digits).zfill(3)
    else:
        return "000"

def create_new_filename(title: str, current_filename: str) -> str:
    """
    Create new filename from title + last 3 digits of current filename
    """
    cleaned_title = clean_title_for_filename(title)
    last_digits = extract_last_three_digits(current_filename)
    
    # Get file extension from current filename
    _, ext = os.path.splitext(current_filename)
    if not ext:
        ext = ".jpg"  # Default extension
    
    return f"{cleaned_title}_{last_digits}{ext}"

async def find_all_metadata_files() -> List[str]:
    """
    Find all metadata.json files in crawl_runs directories
    """
    metadata_files = []
    
    # Check main assets directory
    main_metadata = "assets/metadata.json"
    if os.path.exists(main_metadata):
        metadata_files.append(main_metadata)
    
    # Check crawl_runs directories
    crawl_runs_dir = "assets/crawl_runs"
    if os.path.exists(crawl_runs_dir):
        for run_dir in os.listdir(crawl_runs_dir):
            run_path = os.path.join(crawl_runs_dir, run_dir)
            if os.path.isdir(run_path):
                metadata_file = os.path.join(run_path, "metadata.json")
                if os.path.exists(metadata_file):
                    metadata_files.append(metadata_file)
    
    return metadata_files

async def rename_files_in_metadata(metadata_file: str, dry_run: bool = True) -> Dict:
    """
    Rename files based on metadata in a specific metadata file
    """
    print(f"\n📁 Processing: {metadata_file}")
    
    try:
        # Load metadata
        metadata = await load_metadata(metadata_file)
        if not metadata:
            print(f"❌ No metadata found in {metadata_file}")
            return {"processed": 0, "renamed": 0, "errors": 0}
        
        print(f"📄 Found {len(metadata)} items in metadata")
        
        renamed_count = 0
        error_count = 0
        categories_updated = {}
        
        for i, item in enumerate(metadata):
            try:
                current_filename = item.get('filename', '')
                current_path = item.get('local_path', '')
                title = item.get('title', '')
                category = item.get('category', '')
                
                if not current_filename or not current_path or not os.path.exists(current_path):
                    print(f"⚠️  Skipping item {i+1}: File not found or invalid data")
                    error_count += 1
                    continue
                
                # Create new filename and category
                new_filename = create_new_filename(title, current_filename)
                new_category = clean_category(category)
                
                # Update category tracking
                if category != new_category:
                    categories_updated[category] = new_category
                
                # Create new path
                current_dir = os.path.dirname(current_path)
                # Replace the category part in the path if needed
                if category != new_category:
                    # Extract base images directory and create new category path
                    path_parts = current_path.split(os.sep)
                    # Find 'images' in the path and replace the next part (category)
                    try:
                        images_idx = path_parts.index('images')
                        if images_idx + 1 < len(path_parts):
                            path_parts[images_idx + 1] = new_category
                            new_dir = os.sep.join(path_parts[:-1])  # All except filename
                        else:
                            new_dir = current_dir
                    except ValueError:
                        new_dir = current_dir
                else:
                    new_dir = current_dir
                
                new_path = os.path.join(new_dir, new_filename)
                
                # Print what will be done
                print(f"\n📝 Item {i+1}/{len(metadata)}:")
                print(f"   Title: '{title}'")
                print(f"   Current: {current_filename}")
                print(f"   New: {new_filename}")
                print(f"   Category: '{category}' → '{new_category}'")
                
                if current_filename == new_filename and category == new_category:
                    print(f"   ⏭️  No changes needed")
                    continue
                
                if not dry_run:
                    # Create new directory if needed
                    Path(new_dir).mkdir(parents=True, exist_ok=True)
                    
                    # Handle filename conflicts
                    counter = 1
                    final_new_path = new_path
                    while os.path.exists(final_new_path) and final_new_path != current_path:
                        name, ext = os.path.splitext(new_filename)
                        conflict_filename = f"{name}_conflict_{counter}{ext}"
                        final_new_path = os.path.join(new_dir, conflict_filename)
                        counter += 1
                    
                    # Rename the file
                    if final_new_path != current_path:
                        shutil.move(current_path, final_new_path)
                        print(f"   ✅ Moved: {current_path} → {final_new_path}")
                    
                    # Update metadata
                    item['filename'] = os.path.basename(final_new_path)
                    item['local_path'] = final_new_path
                    item['category'] = new_category
                    
                    renamed_count += 1
                else:
                    print(f"   🔍 DRY RUN: Would rename to {new_path}")
                    
            except Exception as e:
                print(f"❌ Error processing item {i+1}: {e}")
                error_count += 1
        
        # Save updated metadata if not dry run
        if not dry_run and renamed_count > 0:
            await save_metadata(metadata, metadata_file)
            print(f"\n💾 Updated metadata saved to: {metadata_file}")
        
        # Clean up empty directories if not dry run
        if not dry_run:
            try:
                # Get the base images directory from the metadata file path
                base_dir = os.path.dirname(metadata_file)
                images_dir = os.path.join(base_dir, "images")
                
                for root, dirs, files in os.walk(images_dir, topdown=False):
                    for dir_name in dirs:
                        dir_path = os.path.join(root, dir_name)
                        try:
                            if not os.listdir(dir_path):  # Empty directory
                                os.rmdir(dir_path)
                                print(f"🗑️  Removed empty directory: {dir_path}")
                        except OSError:
                            pass  # Directory not empty or other issue
            except Exception as e:
                print(f"⚠️  Error cleaning empty directories: {e}")
        
        if categories_updated:
            print(f"\n📁 Categories updated:")
            for old_cat, new_cat in categories_updated.items():
                print(f"   '{old_cat}' → '{new_cat}'")
        
        return {
            "processed": len(metadata),
            "renamed": renamed_count,
            "errors": error_count,
            "categories_updated": len(categories_updated)
        }
        
    except Exception as e:
        print(f"❌ Error processing {metadata_file}: {e}")
        return {"processed": 0, "renamed": 0, "errors": 1}

async def main():
    """
    Main function to rename files across all metadata files
    """
    print("🎨 File Renaming Tool")
    print("=" * 60)
    print("This tool will:")
    print("✅ Rename files to: [cleaned_title]_[last3digits].jpg")
    print("✅ Clean categories (lowercase, no accents, no underscores)")
    print("✅ Update all metadata files")
    print("✅ Move files to cleaned category folders")
    print("=" * 60)
    
    # Find all metadata files
    metadata_files = await find_all_metadata_files()
    
    if not metadata_files:
        print("❌ No metadata files found!")
        return
    
    print(f"📂 Found {len(metadata_files)} metadata files:")
    for i, file in enumerate(metadata_files, 1):
        print(f"   {i}. {file}")
    
    print("\n" + "=" * 60)
    
    # Ask for confirmation
    response = input("Run in DRY RUN mode first? (Y/n): ").strip().lower()
    dry_run = response != 'n'
    
    if dry_run:
        print("\n🔍 DRY RUN MODE - No files will be changed")
    else:
        print("\n🚀 LIVE MODE - Files will be renamed!")
        confirm = input("Are you sure? Type 'yes' to proceed: ").strip().lower()
        if confirm != 'yes':
            print("❌ Operation cancelled")
            return
    
    print("\n" + "=" * 60)
    
    # Process each metadata file
    total_stats = {"processed": 0, "renamed": 0, "errors": 0, "categories_updated": 0}
    
    for metadata_file in metadata_files:
        stats = await rename_files_in_metadata(metadata_file, dry_run)
        total_stats["processed"] += stats["processed"]
        total_stats["renamed"] += stats["renamed"]
        total_stats["errors"] += stats["errors"]
        total_stats["categories_updated"] += stats.get("categories_updated", 0)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"Files processed: {total_stats['processed']}")
    print(f"Files renamed: {total_stats['renamed']}")
    print(f"Categories cleaned: {total_stats['categories_updated']}")
    print(f"Errors: {total_stats['errors']}")
    
    if dry_run and total_stats['renamed'] > 0:
        print(f"\n💡 To apply changes, run again and choose 'n' for dry run mode")
    elif not dry_run:
        print(f"\n✅ File renaming completed successfully!")
    
    print("\n📝 Filename format: [cleaned_title]_[last3digits].jpg")
    print("📁 Category format: lowercase-no-accents-no-underscores")

if __name__ == "__main__":
    asyncio.run(main()) 