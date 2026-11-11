from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup


class WebCrawler:
    def __init__(self, startUrl):
        parsed = urlparse(startUrl)
        self.domain = f"{parsed.scheme}://{parsed.netloc}"

    def crawl_urls(self, start_url, max_depth):
        visited_urls = set()
        all_urls = []

        def strip_query_params(url):
            parsed = urlparse(url)
            # print(parsed.netloc)
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        def _crawl(url, depth):
            if not url.startswith(self.domain):
                return
            normalized_url = strip_query_params(url)
            if normalized_url in visited_urls:
                return
            if depth > max_depth:
                return
            visited_urls.add(normalized_url)
            # print(url)
            all_urls.append(url)
            try:
                response = requests.get(url)
            except Exception as e:
                print(f"Failed to fetch {url}. Reason: {e}")
                return
            if response.status_code != 200:
                return
            soup = BeautifulSoup(response.text, "html.parser")
            for a_tag in soup.find_all("a"):
                new_url = a_tag.get("href")
                if new_url:
                    new_url = urljoin(url, new_url)
                    if not new_url.startswith(url):
                        continue
                    _crawl(new_url, depth + 1)

        _crawl(start_url, 0)
        return all_urls
