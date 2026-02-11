# Selenium Plugin Setup Guide

## Overview
Three plugins (Anna's Archive, Standard Ebooks, ManyBooks) use Selenium for headless browser automation to handle JavaScript-rendered content.

## Installation Steps

### 1. Install Selenium
Since you're using macOS with Homebrew's Python, use one of these methods:

**Option A: Install with --break-system-packages (Quick)**
```bash
pip3 install selenium --break-system-packages
```

**Option B: Use a virtual environment (Recommended)**
```bash
cd /Users/sebastianmensink/Downloads/newznabarr-master
python3 -m venv venv
source venv/bin/activate
pip install selenium
# Run app from venv: python app.py
```

**Option C: Use pipx**
```bash
brew install pipx
pipx install selenium
```

### 2. Install Chrome Browser
```bash
brew install --cask google-chrome
```

### 3. Install ChromeDriver
```bash
brew install chromedriver
```

### 4. Verify Installation
```bash
python3 -c "from selenium import webdriver; print('✓ Selenium installed')"
chromedriver --version
```

## Enabling Selenium Plugins

1. Start the application
2. Navigate to Settings (⚙️ link on dashboard)
3. Enable desired plugins:
   - **Anna's Archive**: Aggregates multiple sources
   - **Standard Ebooks**: High-quality formatted classics  
   - **ManyBooks**: 50K+ free books
4. Click "Save Settings"
5. Restart the application

## Performance Notes

**Selenium plugins are slower:**
- ~2-5 seconds per search (vs <1s for API-based plugins)
- Uses more memory (headless browser)
- Requires Chrome/ChromeDriver maintenance

**Recommendation:** Start with API-based plugins (LibGen, Open Library, Gutendex) and only enable Selenium plugins if you need their specific content.

## Troubleshooting

### "chromedriver cannot be opened"
```bash
xattr -d com.apple.quarantine $(which chromedriver)
```

### ChromeDriver version mismatch
Make sure ChromeDriver matches your Chrome version:
```bash
google-chrome --version
chromedriver --version
```

If mismatched, update ChromeDriver:
```bash
brew upgrade chromedriver
```

### Selenium not found
Install in the same Python environment where you run the app.
