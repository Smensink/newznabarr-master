#!/bin/bash
# Install Selenium and dependencies for headless Chrome automation

echo "Installing Selenium..."
pip3 install selenium

echo ""
echo "Checking for Chrome and ChromeDriver..."

# Check if Chrome is installed
if command -v google-chrome &> /dev/null || command -v chromium &> /dev/null; then
    echo "✓ Chrome/Chromium found"
else
    echo "⚠️  Chrome not found. Install Chrome browser first."
fi

# Check if chromedriver is installed
if command -v chromedriver &> /dev/null; then
    echo "✓ ChromeDriver found"
    chromedriver --version
else
    echo "⚠️  ChromeDriver not found"
    echo ""
    echo "Install ChromeDriver with:"
    echo "  brew install chromedriver  # macOS"
    echo "  Or download from: https://chromedriver.chromium.org/"
fi

echo ""
echo "Testing Selenium setup..."
python3 -c "from selenium import webdriver; from selenium.webdriver.chrome.options import Options; opts = Options(); opts.add_argument('--headless'); driver = webdriver.Chrome(options=opts); driver.quit(); print('✓ Selenium setup working!')" 2>&1

echo ""
echo "If the test passed, you're ready to use Selenium plugins!"
echo "Enable them in Settings page: Anna's Archive, Standard Ebooks, ManyBooks"
