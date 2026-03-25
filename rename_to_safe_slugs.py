#!/usr/bin/env python3
"""
Rename all preview site folders from Hebrew to URL-safe ASCII slugs.
Creates a mapping file for updating Monday.com links.
"""

import os
import re
import json
import unicodedata

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

# Hebrew to Latin transliteration map
HEBREW_MAP = {
    'א': 'a', 'ב': 'b', 'ג': 'g', 'ד': 'd', 'ה': 'h',
    'ו': 'v', 'ז': 'z', 'ח': 'ch', 'ט': 't', 'י': 'y',
    'כ': 'k', 'ך': 'k', 'ל': 'l', 'מ': 'm', 'ם': 'm',
    'נ': 'n', 'ן': 'n', 'ס': 's', 'ע': 'a', 'פ': 'p',
    'ף': 'f', 'צ': 'ts', 'ץ': 'ts', 'ק': 'k', 'ר': 'r',
    'ש': 'sh', 'ת': 't',
    # Arabic
    'ق': 'q', 'ا': 'a', 'ع': 'a', 'ة': 'h', 'م': 'm',
    'ن': 'n', 'ت': 't', 'ز': 'z', 'ه': 'h', 'و': 'w',
    'ي': 'y', 'ف': 'f', 'ل': 'l', 'ك': 'k', 'د': 'd',
    'ح': 'h', 'ج': 'j', 'ب': 'b', 'ر': 'r', 'س': 's',
    'ش': 'sh', 'ص': 's', 'ض': 'd', 'ط': 't', 'ظ': 'z',
    'غ': 'gh', 'خ': 'kh', 'ث': 'th', 'ذ': 'dh',
    'آ': 'a', 'أ': 'a', 'إ': 'i', 'ء': '', 'ئ': '',
}

# Special chars to remove
SPECIAL_REMOVE = {'״', '׳', '–', '\u200e', '\u200f', '\u202a', '\u202b', '\u202c'}


def transliterate(text):
    """Convert Hebrew/Arabic text to ASCII."""
    result = []
    for ch in text:
        if ch in HEBREW_MAP:
            result.append(HEBREW_MAP[ch])
        elif ch in SPECIAL_REMOVE:
            continue
        elif ord(ch) < 128:
            result.append(ch)
        else:
            # Skip unknown unicode chars
            continue
    return ''.join(result)


def make_safe_slug(folder_name):
    """Convert folder name to URL-safe ASCII slug."""
    # Skip index.html
    if folder_name == 'index.html':
        return None

    # Check if already fully ASCII
    if all(ord(c) < 128 for c in folder_name):
        return folder_name  # Already safe

    # Strategy: transliterate the whole thing, then clean up
    slug = transliterate(folder_name)

    # Clean up: collapse multiple dashes, strip leading/trailing dashes
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')

    # Lowercase for consistency
    slug = slug.lower()

    # Remove any remaining non-alphanumeric except dash and apostrophe
    slug = re.sub(r"[^a-z0-9\-']", '', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')

    # If slug is empty or too short, use a hash
    if len(slug) < 3:
        import hashlib
        slug = 'site-' + hashlib.md5(folder_name.encode()).hexdigest()[:8]

    return slug


def main():
    folders = sorted(os.listdir(OUTPUT_DIR))
    mapping = {}  # old_name -> new_name
    new_names_seen = {}  # detect collisions

    for folder in folders:
        if folder == 'index.html':
            continue
        full_path = os.path.join(OUTPUT_DIR, folder)
        if not os.path.isdir(full_path):
            continue

        new_name = make_safe_slug(folder)
        if new_name == folder:
            # Already safe
            mapping[folder] = folder
            new_names_seen[new_name] = folder
            continue

        # Handle collisions
        base = new_name
        counter = 2
        while new_name in new_names_seen:
            new_name = f"{base}-{counter}"
            counter += 1

        mapping[folder] = new_name
        new_names_seen[new_name] = folder

    # Print summary
    renames = {k: v for k, v in mapping.items() if k != v}
    print(f"Total folders: {len(mapping)}")
    print(f"Already safe: {len(mapping) - len(renames)}")
    print(f"Need rename: {len(renames)}")

    # Save mapping
    mapping_path = os.path.join(os.path.dirname(__file__), "slug_mapping.json")
    with open(mapping_path, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    print(f"\nMapping saved to {mapping_path}")

    # Show renames
    print("\n--- Renames ---")
    for old, new in sorted(renames.items()):
        print(f"  {old}")
        print(f"    -> {new}")

    # Confirm and do renames
    print(f"\nProceeding with {len(renames)} renames...")
    for old, new in renames.items():
        old_path = os.path.join(OUTPUT_DIR, old)
        new_path = os.path.join(OUTPUT_DIR, new)
        if os.path.exists(new_path):
            print(f"  SKIP (target exists): {old} -> {new}")
            continue
        os.rename(old_path, new_path)
        print(f"  OK: {old} -> {new}")

    print("\nDone!")


if __name__ == '__main__':
    main()
