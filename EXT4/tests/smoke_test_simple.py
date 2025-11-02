import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.ext4fs import Ext4FS
import os

def run_smoke_test():
    print("Running simple smoke test...")
    
    # Create filesystem instance
    fs = Ext4FS()
    
    # Test that all methods are accessible
    methods = [
        'open',
        'close', 
        'listdir',
        'stat',
        'read',
        'write_overwrite',
        'mkdirs',
        'remove',
        'rename',
        'mkfs'
    ]
    
    for method in methods:
        if hasattr(fs, method):
            print(f"✓ Method '{method}' is available")
        else:
            print(f"✗ Method '{method}' is missing")
            return False
    
    print("All methods are available!")
    return True

if __name__ == "__main__":
    try:
        success = run_smoke_test()
        with open('../build_logs/smoke_test_simple.log', 'w') as f:
            if success:
                f.write('Simple smoke test passed!\n')
            else:
                f.write('Simple smoke test failed!\n')
        print("Test results written to build_logs/smoke_test_simple.log")
    except Exception as e:
        print(f"Test failed with exception: {e}")