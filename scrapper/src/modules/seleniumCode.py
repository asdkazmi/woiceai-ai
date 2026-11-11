import traceback
from concurrent.futures import ThreadPoolExecutor
import re

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def process_url(url):
    """
    Loads a webpage using a headless Chrome browser, extracts the HTML content,
    and returns the cleaned text content of the page.
    :param url:
    :return:
    """
    try:
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1280x1696')
        chrome_options.add_argument('--user-data-dir=/tmp/user-data')
        chrome_options.add_argument('--hide-scrollbars')
        chrome_options.add_argument('--enable-logging')
        chrome_options.add_argument('--log-level=0')
        chrome_options.add_argument('--v=99')
        chrome_options.add_argument('--single-process')
        chrome_options.add_argument('--data-path=/tmp/data-path')
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--homedir=/tmp')
        chrome_options.add_argument('--disk-cache-dir=/tmp/cache-dir')
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36')
        # chrome_options.add_argument("--headless")
        chrome_options.binary_location = "/bin/headless-chromium"
        driver = webdriver.Chrome("/bin/chromedriver", chrome_options=chrome_options)
        logger.info("Drivers loaded")
        try:
            driver.get(url)
            logger.info("Page loaded successfully")
            WebDriverWait(driver, 60)
            blocked_patterns = ["denied", "no entry", "blocked", "not found", " page not found"]
            page_title = driver.title
            logger.info(f"{page_title}")

            if page_title and not any(re.search(pattern, page_title, re.IGNORECASE) for pattern in blocked_patterns):
                html_content = driver.page_source
                logger.info("Scraping...")
                soup = BeautifulSoup(html_content, "html.parser")
                # found_content = re.sub(r'\\n|\\|\n|\t|\\t', '', soup.text)
                found_content = soup.text.replace("\\\\", "\\")
                cleaned = ' '.join(found_content.split())
                driver.quit()
                return cleaned

            elif any(re.search(pattern, page_title, re.IGNORECASE) for pattern in blocked_patterns):
                logger.info("Nothing found returning empty")
                return ""

        except WebDriverException as e:
            logger.info("Failed to load page:", e)
            return ""

    except:
        logger.error(traceback.format_exc())
        return ""


def process_urls_with_threading(urls):
    """
    Scrapes a list of URLs concurrently using a thread pool and returns a dictionary of scrapped data and a list of
    failed URLs.
    :param urls:
    :return:
    """
    urls = list(set(urls))
    scrapped_data = dict()
    failed_urls = list()
    logger.info("Scraping")
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = executor.map(lambda url: process_url(url), urls)
        for url, result in zip(urls, results):
            if result != "":
                scrapped_data[url] = result
            else:
                failed_urls.append(url)

    return scrapped_data, failed_urls
