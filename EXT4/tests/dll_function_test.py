import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.ext4fs import Ext4FS
import ctypes

def run_dll_function_test():
    print("Running DLL function test...")
    
    try:
        # Create filesystem instance
        fs = Ext4FS()
        
        # Load the library
        fs._load_library()
        print("DLL loaded successfully")
        
        # Check that all required functions are available
        required_functions = [
            'ext4_open',
            'ext4_close',
            'ext4_listdir',
            'ext4_stat',
            'ext4_read',
            'ext4_write_overwrite',
            'ext4_mkdirs',
            'ext4_remove',
            'ext4_rename',
            'ext4_mkfs'
        ]
        
        for func_name in required_functions:
            if hasattr(fs._dll, func_name):
                print(f"✓ Function '{func_name}' is available")
            else:
                print(f"✗ Function '{func_name}' is missing")
                return False
        
        print("All required functions are available!")
        return True
        
    except Exception as e:
        print(f"DLL function test failed: {e}")
        return False

if __name__ == "__main__":
    try:
        success = run_dll_function_test()
        with open('../build_logs/dll_function_test.log', 'w') as f:
            if success:
                f.write('DLL function test passed!\n')
            else:
                f.write('DLL function test failed!\n')
        print("Test results written to build_logs/dll_function_test.log")
    except Exception as e:
        print(f"Test failed with exception: {e}")