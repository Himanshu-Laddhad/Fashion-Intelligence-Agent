"""
Firecrawl Configuration
"""

FIRECRAWL_API_KEY = "fc-674263963d2e416d8395037d12018cf3"

# Scraping options for different sources
SCRAPE_OPTIONS = {
    "pinterest": {
        "formats": ["html"],
        "onlyMainContent": False,
        "waitFor": 2000,
        "timeout": 15000
    },
    "zara": {
        "formats": ["html", "markdown"],
        "onlyMainContent": True,
        "waitFor": 3000,
        "timeout": 20000
    },
    "uniqlo": {
        "formats": ["html"],
        "onlyMainContent": True,
        "waitFor": 2000,
        "timeout": 15000
    },
    "vogue": {
        "formats": ["markdown"],
        "onlyMainContent": True,
        "timeout": 10000
    }
}