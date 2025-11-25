# Save as: make_essential_zip.py
import os
import zipfile
from pathlib import Path
from typing import Set

def iter_essential_files(root: Path):
    """Yield only essential code/config files, skip outputs and legacy."""
    
    SKIP_DIRS = {
        '.git', '__pycache__', '.venv', '.venv311', '.mypy_cache',
        '.pytest_cache', 'outputs', 'exports', 'legacy', 'dutchbay_v13',
        'tests_v13', 'tests_legacy_v13', 'old models'
    }
    
    INCLUDE_EXTS = {
        '.py', '.yaml', '.yml', '.toml', '.ini', '.txt', '.md', '.json'
    }
    
    MAX_FILE_SIZE = 500_000  # 500 KB - skip large CSVs/Excel
    
    for current_root, dirs, files in os.walk(root):
        current_path = Path(current_root)
        
        # Filter directories
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
        
        # Filter files
        for f in files:
            file_path = current_path / f
            
            # Check extension
            if file_path.suffix.lower() not in INCLUDE_EXTS:
                continue
            
            # Check size
            try:
                if file_path.stat().st_size > MAX_FILE_SIZE:
                    print(f"  Skipping large file: {file_path.relative_to(root)} "
                          f"({file_path.stat().st_size:,} bytes)")
                    continue
            except:
                continue
            
            yield file_path

def make_essential_zip(root: Path, output_name: str) -> None:
    """Create lean zip with only code and configs."""
    
    output = root / output_name
    files_added = 0
    total_size = 0
    
    print(f"Creating essential zip: {output}")
    print("Excluding: outputs/, exports/, legacy/, large files (>500KB)")
    print()
    
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for file_path in iter_essential_files(root):
            rel_path = file_path.relative_to(root)
            zf.write(file_path, rel_path.as_posix())
            
            size = file_path.stat().st_size
            total_size += size
            files_added += 1
            
            if files_added % 50 == 0:
                print(f"  Added {files_added} files...")
    
    zip_size = output.stat().st_size
    
    print(f"\n✓ Essential zip created!")
    print(f"  Files: {files_added}")
    print(f"  Uncompressed: {total_size:,} bytes ({total_size/1024/1024:.2f} MB)")
    print(f"  Compressed: {zip_size:,} bytes ({zip_size/1024/1024:.2f} MB)")
    print(f"  Compression: {(1 - zip_size/total_size)*100:.1f}%")
    
    # Clean attributes immediately
    print(f"\n  Removing extended attributes...")
    os.system(f'xattr -c "{output}"')
    print(f"  ✓ Clean zip ready for upload")

if __name__ == "__main__":
    root = Path.cwd()
    make_essential_zip(root, "DutchBay_v14_essential.zip")


