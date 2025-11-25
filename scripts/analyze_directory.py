#!/usr/bin/env python3
"""
Directory Structure Analyzer
Traverses a root folder and generates a structured JSON view with:
- Folder/subfolder hierarchy
- File names and sizes
- Python file imports and dependencies
"""

import os
import json
import ast
from pathlib import Path
from typing import Dict, List, Any
import sys

def get_python_imports(file_path: str) -> Dict[str, List[str]]:
    """Extract imports from a Python file."""
    imports = {
        'stdlib': [],
        'third_party': [],
        'local': []
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=file_path)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports['third_party'].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                if module.startswith('.'):
                    imports['local'].append(module)
                else:
                    imports['third_party'].append(module)
    
    except Exception as e:
        imports['error'] = str(e)
    
    return imports

def analyze_directory(root_path: str, include_hidden: bool = False) -> Dict[str, Any]:
    """
    Recursively analyze directory structure.
    
    Args:
        root_path: Root directory to analyze
        include_hidden: Include hidden files/folders (starting with .)
    
    Returns:
        Dictionary containing directory structure and metadata
    """
    root = Path(root_path).resolve()
    
    def traverse(path: Path) -> Dict[str, Any]:
        result = {
            'name': path.name,
            'path': str(path.relative_to(root)),
            'absolute_path': str(path),
            'type': 'directory' if path.is_dir() else 'file'
        }
        
        if path.is_file():
            result['size_bytes'] = path.stat().st_size
            result['size_human'] = format_size(path.stat().st_size)
            result['extension'] = path.suffix
            
            # Extract imports for Python files
            if path.suffix == '.py':
                result['imports'] = get_python_imports(str(path))
        
        elif path.is_dir():
            children = []
            try:
                for item in sorted(path.iterdir()):
                    # Skip hidden files/folders if not included
                    if not include_hidden and item.name.startswith('.'):
                        continue
                    children.append(traverse(item))
                
                result['children'] = children
                result['total_files'] = sum(1 for c in children if c['type'] == 'file')
                result['total_subdirs'] = sum(1 for c in children if c['type'] == 'directory')
                
            except PermissionError:
                result['error'] = 'Permission denied'
                result['children'] = []
        
        return result
    
    return traverse(root)

def format_size(size_bytes: int) -> str:
    """Format bytes to human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

def generate_summary(structure: Dict[str, Any]) -> Dict[str, Any]:
    """Generate summary statistics."""
    def count_items(node: Dict[str, Any]) -> Dict[str, int]:
        counts = {'files': 0, 'directories': 0, 'python_files': 0, 'total_size': 0}
        
        if node['type'] == 'file':
            counts['files'] = 1
            counts['total_size'] = node.get('size_bytes', 0)
            if node.get('extension') == '.py':
                counts['python_files'] = 1
        elif node['type'] == 'directory':
            counts['directories'] = 1
            for child in node.get('children', []):
                child_counts = count_items(child)
                for key in counts:
                    counts[key] += child_counts[key]
        
        return counts
    
    counts = count_items(structure)
    return {
        'total_files': counts['files'],
        'total_directories': counts['directories'],
        'python_files': counts['python_files'],
        'total_size_bytes': counts['total_size'],
        'total_size_human': format_size(counts['total_size'])
    }

def main():
    """Main execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Analyze directory structure and generate JSON output'
    )
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='Root directory path to analyze (default: current directory)'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output JSON file path (default: print to stdout)'
    )
    parser.add_argument(
        '-i', '--include-hidden',
        action='store_true',
        help='Include hidden files and folders'
    )
    parser.add_argument(
        '--pretty',
        action='store_true',
        help='Pretty print JSON output'
    )
    
    args = parser.parse_args()
    
    # Analyze directory
    print(f"Analyzing directory: {args.path}", file=sys.stderr)
    structure = analyze_directory(args.path, args.include_hidden)
    summary = generate_summary(structure)
    
    # Prepare output
    output = {
        'root': args.path,
        'summary': summary,
        'structure': structure
    }
    
    # Format JSON
    indent = 2 if args.pretty else None
    json_output = json.dumps(output, indent=indent)
    
    # Write output
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(json_output)
        print(f"Output written to: {args.output}", file=sys.stderr)
    else:
        print(json_output)

if __name__ == '__main__':
    main()
