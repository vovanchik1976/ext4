import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.ext4fs import Ext4FS
import os

def run_filesystem_existing_test():
    print("Running filesystem test with existing image...")
    
    # Check if we have an existing ext4 image
    existing_images = [
        'test_image.ext4',
        'test_image.img',
        'sample.ext4',
        'sample.img'
    ]
    
    image_path = None
    for img in existing_images:
        if os.path.exists(img):
            image_path = img
            break
    
    if not image_path:
        print("No existing ext4 image found. Please provide an ext4 image for testing.")
        return False
    
    fs = Ext4FS()
    
    try:
        # Open it for read/write
        print(f"Opening filesystem from {image_path}...")
        fs.open(image_path, rw=True)
        print("Filesystem opened successfully")
        
        # List root directory
        print("Listing root directory...")
        items = fs.listdir('/')
        print(f"Root directory items: {items}")
        
        # Close filesystem
        print("Closing filesystem...")
        fs.close()
        print("Filesystem closed successfully")
        
        print("Filesystem test with existing image passed!")
        return True
        
    except Exception as e:
        print(f"Filesystem test with existing image failed: {e}")
        return False

if __name__ == "__main__":
    try:
        success = run_filesystem_existing_test()
        with open('../build_logs/filesystem_existing_test.log', 'w') as f:
            if success:
                f.write('Filesystem test with existing image passed!\n')
            else:
                f.write('Filesystem test with existing image failed!\n')
        print("Test results written to build_logs/filesystem_existing_test.log")
    except Exception as e:
        print(f"Test failed with exception: {e}")