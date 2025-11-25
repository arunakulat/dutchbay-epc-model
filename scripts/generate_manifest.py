#!/usr/bin/env python3
"""Generate manifest from an existing zip file."""

import sys
import json
import zipfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

def create_manifest_from_zip(zip_path: Path) -> Dict[str, Any]:
    """Extract file list from existing zip and create manifest."""
    
    manifest = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "zip_file": str(zip_path.name),
            "zip_size_bytes": zip_path.stat().st_size,
        },
        "files": []
    }
    
    total_uncompressed = 0
    
    with zipfile.ZipFile(zip_path, 'r') as zf:
        file_list = zf.infolist()
        manifest["metadata"]["total_files"] = len([f for f in file_list if not f.is_dir()])
        
        for info in file_list:
            if info.is_dir():
                continue
                
            file_info = {
                "path": info.filename,
                "size_bytes": info.file_size,
                "compressed_size_bytes": info.compress_size,
                "modified_at": datetime(*info.date_time).isoformat(),
                "extension": Path(info.filename).suffix.lower(),
            }
            manifest["files"].append(file_info)
            total_uncompressed += info.file_size
    
    manifest["metadata"]["total_uncompressed_bytes"] = total_uncompressed
    
    if total_uncompressed > 0:
        ratio = (1 - manifest["metadata"]["zip_size_bytes"] / total_uncompressed) * 100
        manifest["metadata"]["compression_ratio_percent"] = round(ratio, 2)
    
    return manifest

def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(f"Usage: {argv[0]} <existing_zipfile>", file=sys.stderr)
        return 1
    
    zip_path = Path(argv[1])
    
    if not zip_path.exists():
        print(f"Error: {zip_path} not found", file=sys.stderr)
        return 1
    
    manifest = create_manifest_from_zip(zip_path)
    manifest_path = zip_path.with_suffix('.json')
    
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Manifest created: {manifest_path}")
    print(f"  Files: {manifest['metadata']['total_files']}")
    print(f"  Size: {manifest['metadata']['total_uncompressed_bytes']:,} → "
          f"{manifest['metadata']['zip_size_bytes']:,} bytes")
    print(f"  Compression: {manifest['metadata'].get('compression_ratio_percent', 0):.1f}%")
    
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))