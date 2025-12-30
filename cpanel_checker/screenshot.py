"""Screenshot capture and comparison utilities."""

import os
import glob
import logging
import time
import colorsys
from PIL import Image
import imagehash
import numpy as np

class ScreenshotManager:
    """Manages screenshot capture, resizing, and comparison."""

    # Perceptual hash distance threshold - lower values mean more similar
    # Hash distance of 5 or less is considered "identical" for perceptual hash
    # This is more robust to imperceptible changes in photographs than SSIM
    HASH_DISTANCE_THRESHOLD = 5

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
        """Compare two screenshots using perceptual hashing and optionally create a diff image.

        Uses perceptual hash (phash) which is robust to imperceptible changes in photographs.
        Hash distance is used as a metric: lower values mean more similar images.

        Args:
            img1_path: Path to first (newer) screenshot
            img2_path: Path to second (older) screenshot
            diff_output_path: Optional path to save diff image

        Returns:
            int: Hash distance (0 = identical, higher = more different) or None if comparison failed
        """
        try:
            img1 = Image.open(img1_path)
            img2 = Image.open(img2_path)

            # Calculate perceptual hashes
            hash1 = imagehash.phash(img1)
            hash2 = imagehash.phash(img2)

            # Calculate hash distance (0 = identical, higher = more different)
            hash_distance = hash1 - hash2

            # Create diff image if requested and images are different
            if diff_output_path and hash_distance > self.HASH_DISTANCE_THRESHOLD:
                # Ensure both images are the same size for diff visualization
                if img1.size != img2.size:
                    img2 = img2.resize(img1.size, Image.LANCZOS)

                # Convert to RGB arrays for visualization
                img1_rgb = img1.convert("RGB")
                img2_rgb = img2.convert("RGB")
                arr1 = np.array(img1_rgb)
                arr2 = np.array(img2_rgb)

                # Calculate pixel-wise differences
                diff = np.abs(arr1.astype(float) - arr2.astype(float))
                
                # Normalize difference to 0-255 range
                max_diff = np.max(diff)
                if max_diff > 0:
                    diff_normalized = (diff / max_diff * 255).astype(np.uint8)
                else:
                    diff_normalized = diff.astype(np.uint8)

                # Create red overlay where differences exist
                # Average across color channels to get overall difference
                diff_gray = np.mean(diff_normalized, axis=2).astype(np.uint8)

                # Create red overlay (semi-transparent)
                red_overlay = np.zeros_like(arr1)
                red_overlay[:, :, 0] = diff_gray  # Red channel

                # Blend with alpha
                alpha = 0.6
                result = arr1.astype(float)
                result[:, :, 0] = (1 - alpha) * result[:, :, 0] + alpha * red_overlay[:, :, 0]
                result = result.astype(np.uint8)

                # Save diff image
                diff_img = Image.fromarray(result)
                diff_img.save(diff_output_path)

            return hash_distance
        except Exception as e:
            self.log.error(f"Failed to compare screenshots: {e}")
            return None
