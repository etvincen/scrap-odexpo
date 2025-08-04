"""
Reorganize existing images based on description categories
"""

import asyncio
import os
import shutil
from pathlib import Path
from utils.helpers import load_metadata, clean_description_for_folder, create_directory_structure
import config

async def reorganize_images():
    """Reorganize existing images into category-based folders"""
    print("🔄 Reorganizing images based on categories...")
    
    # Load existing metadata
    metadata = await load_metadata()
    if not metadata:
        print("❌ No metadata found. Run the crawler first.")
        return
    
    print(f"📂 Found {len(metadata)} images to reorganize")
    
    moved_count = 0
    error_count = 0
    categories = {}
    
    for img_data in metadata:
        try:
            current_path = img_data.get('local_path', '')
            description = img_data.get('description', '')
            filename = img_data.get('filename', '')
            
            if not current_path or not os.path.exists(current_path):
                print(f"⚠️  Image file not found: {current_path}")
                error_count += 1
                continue
            
            # Get the new category-based directory
            category = clean_description_for_folder(description)
            new_dir = os.path.join(config.IMAGES_DIR, category)
            Path(new_dir).mkdir(parents=True, exist_ok=True)
            
            new_path = os.path.join(new_dir, filename)
            
            # If the file is already in the right place, skip
            if os.path.abspath(current_path) == os.path.abspath(new_path):
                continue
            
            # Handle filename conflicts
            counter = 1
            original_filename = filename
            while os.path.exists(new_path):
                name, ext = os.path.splitext(original_filename)
                filename = f"{name}_{counter}{ext}"
                new_path = os.path.join(new_dir, filename)
                counter += 1
            
            # Move the file
            shutil.move(current_path, new_path)
            
            # Update metadata
            img_data['local_path'] = new_path
            img_data['filename'] = filename
            img_data['category'] = category
            img_data['cleaned_description'] = category
            
            moved_count += 1
            categories[category] = categories.get(category, 0) + 1
            
            print(f"✅ Moved to [{category}]: {filename}")
            
        except Exception as e:
            print(f"❌ Error moving image: {e}")
            error_count += 1
    
    # Save updated metadata
    if moved_count > 0:
        from utils.helpers import save_metadata
        await save_metadata(metadata)
        print(f"\n📄 Updated metadata saved")
    
    # Clean up empty directories
    try:
        for root, dirs, files in os.walk(config.IMAGES_DIR, topdown=False):
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                if not os.listdir(dir_path):  # Empty directory
                    os.rmdir(dir_path)
                    print(f"🗑️  Removed empty directory: {dir_path}")
    except Exception as e:
        print(f"⚠️  Error cleaning empty directories: {e}")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 REORGANIZATION SUMMARY")
    print("=" * 50)
    print(f"Images moved: {moved_count}")
    print(f"Errors: {error_count}")
    print(f"Categories created: {len(categories)}")
    
    if categories:
        print(f"\n📁 CATEGORIES:")
        for category, count in sorted(categories.items()):
            print(f"  {category}: {count} images")

async def main():
    """Main function"""
    print("🎨 Odexpo Gallery Image Reorganizer")
    print("=" * 50)
    
    # Ask for confirmation
    response = input("This will reorganize all existing images. Continue? (y/N): ")
    if response.lower() != 'y':
        print("❌ Cancelled.")
        return
    
    await reorganize_images()
    print("\n✅ Reorganization complete!")

if __name__ == "__main__":
    asyncio.run(main()) 