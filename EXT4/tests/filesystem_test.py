import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.ext4fs import Ext4FS
import os

def run_filesystem_test():
    print("Running filesystem test...")
    
    # Create test image file path
    IMG = 'test.img'
    
    # Clean up any existing test image
    if os.path.exists(IMG):
        os.remove(IMG)
    
    fs = Ext4FS()
    
    try:
        # Create a filesystem
        print("Creating filesystem...")
        # Try with simpler parameters
        fs.mkfs(IMG, 16 * 1024 * 1024, 1024)  # 16MB, 1024 block size
        print("Filesystem created successfully")
        
        print("Filesystem test passed!")
        return True
        
    except Exception as e:
        print(f"Filesystem test failed: {e}")
        return False
    finally:
        # Clean up
        if os.path.exists(IMG):
            os.remove(IMG)

if __name__ == "__main__":
    try:
        success = run_filesystem_test()
        with open('../build_logs/filesystem_test.log', 'w') as f:
            if success:
                f.write('Filesystem test passed!\n')
            else:
                f.write('Filesystem test failed!\n')
        print("Test results written to build_logs/filesystem_test.log")
    except Exception as e:
        print(f"Test failed with exception: {e}")