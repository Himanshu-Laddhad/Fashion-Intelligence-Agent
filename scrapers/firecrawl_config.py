"""
Firecrawl Configuration
"""

FIRECRAWL_API_KEY = "fc-a4620090c90c4032b593aa9de2945484"

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