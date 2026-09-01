"""
Entity Normalization Service
Standardizes entity names before insertion to avoid duplicates.
"""

import re

_ALIAS_MAP = {
    "vscode": "Visual Studio Code",
    "vs code": "Visual Studio Code",
    "visual studio code": "Visual Studio Code",
    "pycharm": "PyCharm",
    "python": "Python",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "react": "React",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "github": "GitHub",
    "git": "Git",
    "docker": "Docker",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "aws": "AWS",
    "amazon web services": "AWS",
    "google cloud": "Google Cloud Platform",
    "gcp": "Google Cloud Platform",
}

def normalize_entity_name(name: str) -> str:
    """Normalize common entity names to standard forms."""
    if not name:
        return name
    
    cleaned = name.strip()
    lower = cleaned.lower()
    
    if lower in _ALIAS_MAP:
        return _ALIAS_MAP[lower]
    
    return cleaned
