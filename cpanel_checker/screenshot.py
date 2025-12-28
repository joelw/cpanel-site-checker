"""Screenshot capture and comparison utilities."""

import os
import glob
import logging
import time
import colorsys
from PIL import Image
from skimage.metrics import structural_similarity as ssim
import numpy as np

class ScreenshotManager:
    """Manages screenshot capture, resizing, and comparison."""

    # SSIM threshold - values closer to 1.0 mean more similar
    # 0.95 means images must be 95% structurally similar to be considered "identical"
    SSIM_THRESHOLD = 0.95

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
        self.driver.set_window_size(width, height)
        self.driver.get(url)
        time.sleep(5)  # Wait for images to fade in
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

        # Sort by date extracted from path (YYYYMMDDnn), most recent first
        def extract_date(path):
            try:
                # Extract date from path like './2025122801/...'
                parts = path.split(os.sep)
                for part in parts:
                    # Check for YYYYMMDDnn (10 chars) or legacy YYYYMMDD (8 chars)
                    if (len(part) == 10 or len(part) == 8) and part[:8].isdigit():
                        return part
                return '0000000000'  # Fallback for files without date pattern
            except:
                return '0000000000'

        matching_files.sort(key=extract_date, reverse=True)
        return matching_files[0]

    def compare_screenshots(self, img1_path, img2_path, diff_output_path=None):
        """Compare two screenshots and optionally create a diff image.

        Args:
            img1_path: Path to first (newer) screenshot
            img2_path: Path to second (older) screenshot
            diff_output_path: Optional path to save diff image

        Returns:
            float: Difference percentage (0-100) or None if comparison failed
        """
        try:
            img1 = Image.open(img1_path)
            img2 = Image.open(img2_path)

            # Ensure both images are the same size
            if img1.size != img2.size:
                img2 = img2.resize(img1.size, Image.LANCZOS)

            # Convert to grayscale for SSIM comparison
            gray1 = img1.convert("L")
            gray2 = img2.convert("L")

            # Convert to numpy arrays
            arr1 = np.array(gray1)
            arr2 = np.array(gray2)

            # Calculate SSIM
            similarity_index, diff_image = ssim(arr1, arr2, full=True)

            # Create diff image if requested and images are different
            if diff_output_path and similarity_index < self.SSIM_THRESHOLD:
                # Convert diff_image from float to uint8
                diff_image = (diff_image * 255).astype(np.uint8)

                # Convert original to RGB for overlay
                img1_rgb = img1.convert("RGB")
                img1_array = np.array(img1_rgb)

                # Create red overlay where differences exist
                # diff_image ranges from 0 (different) to 255 (same)
                # Invert so differences are highlighted
                mask = 255 - diff_image

                # Create red overlay (semi-transparent)
                red_overlay = np.zeros_like(img1_array)
                red_overlay[:, :, 0] = mask  # Red channel

                # Blend with alpha
                alpha = 0.6
                result = img1_array.astype(float)
                result[:, :, 0] = (1 - alpha) * result[:, :, 0] + alpha * red_overlay[
                    :, :, 0
                ]
                result = result.astype(np.uint8)

                # Save diff image
                diff_img = Image.fromarray(result)
                diff_img.save(diff_output_path)

            return similarity_index
        except Exception as e:
            self.log.error(f"Failed to compare screenshots: {e}")
            return None
