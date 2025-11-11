"""
JSON Loader Utility for Producer Playground
Dynamically loads JSON files from sample_events directories
"""
import os
import json
from pathlib import Path
from typing import Dict, List, Tuple


def filename_to_display_name(filename: str) -> str:
    """
    Convert filename to user-friendly display name.

    Examples:
        "001-basic-single-item-pricing.json" -> "001 Basic Single Item Pricing"
        "123456-b2b-affiliate-case.json" -> "123456 B2B Affiliate Case"
        "simple-pricing.json" -> "Simple Pricing"

    Args:
        filename: JSON filename (e.g., "001-basic-pricing.json")

    Returns:
        Display-friendly name with capitalized words
    """
    # Remove .json extension
    name = filename.replace('.json', '')

    # Split by hyphens
    parts = name.split('-')

    # Capitalize each part
    capitalized_parts = []
    for part in parts:
        # Special handling for common acronyms
        if part.upper() in ['B2B', 'B2C', 'VAT', 'FX', 'ID', 'API', 'USD', 'IDR']:
            capitalized_parts.append(part.upper())
        else:
            capitalized_parts.append(part.capitalize())

    # Join with spaces
    return ' '.join(capitalized_parts)


def load_json_files_from_directory(directory_path: str) -> List[Tuple[str, str, Dict]]:
    """
    Load all JSON files from a directory.

    Args:
        directory_path: Absolute path to directory containing JSON files

    Returns:
        List of tuples: (display_name, filename, json_content)
        Sorted by filename for consistent ordering
    """
    results = []

    if not os.path.exists(directory_path):
        return results

    # Get all JSON files
    json_files = sorted([f for f in os.listdir(directory_path) if f.endswith('.json')])

    for filename in json_files:
        filepath = os.path.join(directory_path, filename)
        try:
            with open(filepath, 'r') as f:
                content = json.load(f)
                display_name = filename_to_display_name(filename)
                results.append((display_name, filename, content))
        except (json.JSONDecodeError, IOError) as e:
            # Skip files that can't be read
            print(f"Warning: Could not load {filename}: {e}")
            continue

    return results


def get_sample_events_directory(category: str) -> str:
    """
    Get absolute path to a sample_events category directory.

    Args:
        category: One of: pricing_events, payment_timeline,
                 supplier_and_payable_event, refund_timeline, refund_components

    Returns:
        Absolute path to the category directory
    """
    # Get the directory where this file is located
    current_file_dir = Path(__file__).parent

    # Navigate to prototype/sample_events/{category}
    prototype_dir = current_file_dir.parent.parent
    sample_events_dir = prototype_dir / "sample_events" / category

    return str(sample_events_dir)
