import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.ext4fs import Ext4FS
import os

def run_smoke_test():
    IMG = 'test.img'
    
    # Clean up any existing test image
    if os.path.exists(IMG):
        os.remove(IMG)
    
    fs = Ext4FS()
    
    # Create a filesystem
    fs.mkfs(IMG, 64 * 1024 * 1024)
    
    # Open it for read/write
    fs.open(IMG, rw=True)
    
    # Create a directory
    fs.mkdirs('/dir', 0o755)
    
    # Write a file
    fs.write_overwrite('/dir/hello.txt', b'Hello world!', 0o644)
    
    # Read the file
    data = fs.read('/dir/hello.txt')
    assert data == b'Hello world!'
    
    # Check directory listing
    items = fs.listdir('/dir')
    names = [item['name'] for item in items]
    assert 'hello.txt' in names
    
    # Check file stats
    stats = fs.stat('/dir/hello.txt')
    assert stats['type'] == 'file'
    assert stats['size'] == 12
    
    # Rename the file
    fs.rename('/dir/hello.txt', 'hello2.txt')
    
    # Check that old file is gone and new file exists
    items = fs.listdir('/dir')
    names = [item['name'] for item in items]
    assert 'hello.txt' not in names
    assert 'hello2.txt' in names
    
    # Remove the file
    fs.remove('/dir/hello2.txt')
    
    # Check that file is gone
    items = fs.listdir('/dir')
    names = [item['name'] for item in items]
    assert 'hello2.txt' not in names
    
    # Close filesystem
    fs.close()
    
    # Clean up
    if os.path.exists(IMG):
        os.remove(IMG)
    
    print('Smoke test passed!')
    return True

if __name__ == "__main__":
    try:
        success = run_smoke_test()
        with open('../build_logs/test_run.log', 'w') as f:
            if success:
                f.write('Smoke test passed!\n')
            else:
                f.write('Smoke test failed!\n')
    except Exception as e:
        with open('../build_logs/test_run.log', 'w') as f:
            f.write(f'Smoke test failed: {str(e)}\n')
        raise