import logging
import time

import cv2

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def detect_captcha(driver):
    """

    :param driver:
    :return:
    """
    time.sleep(2)
    # Take a screenshot of the webpage
    driver.save_screenshot("img/screenshot.png")

    screenshot = cv2.imread("img/screenshot.png")
    if screenshot is None:
        logger.info("Failed to load image")
        return True

    # Preprocess the image
    gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    thresholded = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

    # Find contours in the thresholded image
    _, contours, _ = cv2.findContours(thresholded.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Iterate through contours and filter out potential captcha regions
    captcha_regions = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w > 100 and h > 50:  # Adjust these thresholds based on captcha size
            captcha_regions.append((x, y, w, h))

    # Check if any of the patterns are present in the title
    if captcha_regions:
        logger.info("CAPTCHA detected/Access denied")
        return True
    else:
        logger.info("No CAPTCHA detected")
        return False
