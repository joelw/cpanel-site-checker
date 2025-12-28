"""Screenshot capture and comparison utilities."""

import os
import glob
import logging
from PIL import Image


class ScreenshotManager:
    """Manages screenshot capture, resizing, and comparison."""
    
    # Threshold for considering screenshots identical (percentage difference)
    SCREENSHOT_IDENTICAL_THRESHOLD = 0.01
    
    def __init__(self, driver, output_dir='.'):
        """Initialize screenshot manager.
        
        Args:
            driver: Selenium WebDriver instance
            output_dir: Base output directory
        """
        self.driver = driver
        self.output_dir = output_dir
        self.log = logging.getLogger(__name__)
    
    def capture_screenshot(self, url, output_path, width=1440, height=2000):
        """Capture a screenshot of a web page.
        
        Args:
            url: URL to capture
            output_path: Path to save screenshot
            width: Browser window width
            height: Browser window height
        """
        self.driver.get(url)
        self.driver.set_window_size(width, height)
        self.driver.save_screenshot(output_path)
    
    def resize_screenshot(self, image_path, width=500):
        """Resize screenshot to thumbnail with specified width, maintaining aspect ratio.
        
        Args:
            image_path: Path to image file
            width: Target width in pixels
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            img = Image.open(image_path)
            
            # Guard against division by zero
            if img.width == 0:
                self.log.error(f"Invalid image width (0) for {image_path}")
                return False
            
            # Calculate new height to maintain aspect ratio
            aspect_ratio = img.height / img.width
            new_height = int(width * aspect_ratio)
            # Resize the image
            img_resized = img.resize((width, new_height), Image.LANCZOS)
            # Save back to the same file
            img_resized.save(image_path)
            return True
        except Exception as e:
            self.log.error(f"Failed to resize screenshot {image_path}: {e}")
            return False
    
    def find_previous_screenshot(self, domain, current_directory):
        """Find the most recent screenshot for a domain from previous runs.
        
        Args:
            domain: Domain name
            current_directory: Current run's directory (to exclude)
        
        Returns:
            str: Path to previous screenshot or None if not found
        """
        # Get all subdirectories in output_dir
        pattern = os.path.join(self.output_dir, '*', '*', f'*-{domain}.png')
        matching_files = glob.glob(pattern)
        
        # Filter out the current directory's file
        matching_files = [f for f in matching_files if not f.startswith(current_directory)]
        
        if not matching_files:
            return None
        
        # Sort by modification time, most recent first
        matching_files.sort(key=os.path.getmtime, reverse=True)
        return matching_files[0]
    
    def compare_screenshots(self, img1_path, img2_path):
        """Compare two screenshots and return the percentage of different pixels.
        
        Args:
            img1_path: Path to the new screenshot (always resized to 500px width)
            img2_path: Path to the previous screenshot (may be old format or resized)
        
        Returns:
            float: Percentage of different pixels, or None if comparison failed
        """
        try:
            img1 = Image.open(img1_path)
            img2 = Image.open(img2_path)
            
            # Ensure both images are the same size
            # img2 is the older screenshot which may have been captured before resize feature
            # img1 is the new screenshot which is always 500px wide
            if img1.size != img2.size:
                # Resize img2 to match img1 (the new resized format)
                img2 = img2.resize(img1.size, Image.LANCZOS)
            
            # Convert to RGB if needed (in case of RGBA or other formats)
            if img1.mode != 'RGB':
                img1 = img1.convert('RGB')
            if img2.mode != 'RGB':
                img2 = img2.convert('RGB')
            
            # Get pixel data
            pixels1 = list(img1.getdata())
            pixels2 = list(img2.getdata())
            
            # Count different pixels
            different_pixels = sum(1 for p1, p2 in zip(pixels1, pixels2) if p1 != p2)
            total_pixels = len(pixels1)
            
            # Calculate percentage
            if total_pixels > 0:
                diff_percentage = (different_pixels / total_pixels) * 100
            else:
                diff_percentage = 0
            
            return diff_percentage
        except Exception as e:
            self.log.error(f"Failed to compare screenshots: {e}")
            return None
