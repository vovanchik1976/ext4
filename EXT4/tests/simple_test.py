import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.ext4fs import Ext4FS
import os

def run_simple_test():
    print("Testing DLL loading...")
    
    # Create filesystem instance
    fs = Ext4FS()
    
    # Test that DLL is loaded (this will fail, but we'll catch the error)
    try:
        fs._load_library()
        print("DLL loaded successfully")
    except Exception as e:
        print(f"Failed to load DLL: {e}")
        return False
    
    print("Simple test completed")
    return True

if __name__ == "__main__":
    try:
        success = run_simple_test()
        # Make sure build_logs directory exists
        os.makedirs('../build_logs', exist_ok=True)
        with open('../build_logs/test_run.log', 'w') as f:
            if success:
                f.write('Simple test passed!\n')
            else:
                f.write('Simple test failed!\n')
        print("Test results written to build_logs/test_run.log")
    except Exception as e:
        print(f"Test failed: {e}")