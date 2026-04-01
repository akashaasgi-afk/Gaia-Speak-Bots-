"""
Pre-flight import patcher — runs before gunicorn to ensure optional
packages that may not be installed don't crash the app at startup.
"""
import re

PATCHES = [
    # sentence_transformers
    (
        r'^from sentence_transformers import SentenceTransformer\s*$',
        'try:\n    from sentence_transformers import SentenceTransformer\nexcept ImportError:\n    SentenceTransformer = None',
    ),
    # schedule
    (
        r'^import schedule\s*$',
        'try:\n    import schedule\n    HAS_SCHEDULE = True\nexcept ImportError:\n    schedule = None\n    HAS_SCHEDULE = False',
    ),
]

def patch(path='main.py'):
    with open(path, 'r') as f:
        content = f.read()

    changed = False
    for pattern, replacement in PATCHES:
        new = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        if new != content:
            content = new
            changed = True
            print(f'[patcher] Applied patch for: {pattern}')

    # Also make sure bare `model = SentenceTransformer(...)` is guarded
    if 'SentenceTransformer' in content and 'SentenceTransformer = None' in content:
        guarded = re.sub(
            r'^(model\s*=\s*SentenceTransformer\()',
            r'model = SentenceTransformer(\nif SentenceTransformer else None\nif False: model = SentenceTransformer(',
            content, flags=re.MULTILINE
        )
        # Simpler: replace the bare assignment
        content = re.sub(
            r'^model\s*=\s*SentenceTransformer\([^)]*\)\s*$',
            'model = SentenceTransformer(\'all-MiniLM-L6-v2\') if SentenceTransformer else None',
            content, flags=re.MULTILINE
        )
        if content != guarded:
            changed = True

    if changed:
        with open(path, 'w') as f:
            f.write(content)
        print('[patcher] main.py patched successfully.')
    else:
        print('[patcher] No patches needed.')

if __name__ == '__main__':
    patch()
