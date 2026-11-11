from urllib.parse import urlparse


def filter_urls(parent_url, urls, max_depth):
    filtered_urls = []
    parsed_url = urlparse(parent_url)
    path_segments = [segment for segment in parsed_url.path.split('/') if segment]
    parent = (len(path_segments))

    for url in urls:
        if url.startswith(parent_url):
            parsed_url = urlparse(url)
            path_segments = [segment for segment in parsed_url.path.split('/') if segment]
            child = (len(path_segments))
            if child - parent <= max_depth:
                filtered_urls.append(url)
    if parent_url in filtered_urls:
        filtered_urls.remove(parent_url)
    return filtered_urls
