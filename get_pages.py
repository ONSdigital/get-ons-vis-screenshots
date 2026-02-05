import json
import re
import requests
import subprocess
import time
import random
import sys
import os
import shutil
from datetime import datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

RESULT_SIZE = 50
ONS_URL = "https://www.ons.gov.uk"
PAGE_LIST_URL = (
    "https://api.beta.ons.gov.uk/v1/search/releases?q=&sort=release_date_desc&limit=" + str(RESULT_SIZE)
    "&offset="
)

def make_ons_url(url_path):
    return urljoin(ONS_URL, url_path)

def get_page(url):
    time.sleep(1.1 + random.random())
    NUM_ATTEMPTS = 11
    for attempt_num in range(NUM_ATTEMPTS):
        print("***", url)
        response = requests.get(url)
        if response.status_code == 200:
            return response.text
        print("Status code", response.status_code, "for", url)
        if attempt_num < NUM_ATTEMPTS - 1:
            sleep_time = attempt_num * attempt_num + 10
            print("Sleeping for", sleep_time)
            time.sleep(sleep_time)
    print("Giving up on", url)
    return ""


def normalize_ons_path(href):
    if not href:
        return None
    href = href.strip()
    if href.startswith("//"):
        parsed = urlparse("https:" + href)
        if parsed.netloc.endswith("ons.gov.uk"):
            return parsed.path
        return None
    parsed = urlparse(href)
    if parsed.scheme and parsed.netloc:
        if parsed.netloc.endswith("ons.gov.uk"):
            return parsed.path
        return None
    if not href.startswith("/"):
        href = "/" + href
    return href


def normalize_release_date(date_str):
    if not date_str:
        return ""
    date_str = date_str.strip()
    if "T" in date_str:
        date_str = date_str.split("T")[0]
    if " " in date_str and date_str[0].isdigit() and ":" in date_str:
        date_str = date_str.split(" ")[0]
    if "/" in date_str:
        parts = date_str.split("/")
        if len(parts) == 3:
            return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def compare_dates(date_a, date_b):
    if not date_a or not date_b:
        return None
    try:
        return datetime.strptime(date_a, "%Y-%m-%d") <= datetime.strptime(date_b, "%Y-%m-%d")
    except ValueError:
        return None


def extract_release_date(html):
    match = re.search(r'dataLayer\[0\]\["releaseDate"\]\s*=\s*"([^"]+)"', html)
    if match:
        return normalize_release_date(match.group(1))
    match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html)
    if match:
        return normalize_release_date(match.group(1))
    match = re.search(r"Release date:\s*</span>\s*<br\s*/?>\s*([^<]+)", html, re.IGNORECASE)
    if match:
        return normalize_release_date(match.group(1))
    return ""


def extract_title(soup):
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
        if title:
            return title
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return ""


def is_document_link(href):
    path = normalize_ons_path(href)
    if not path:
        return False
    if any(ext in path for ext in [".pdf", ".xls", ".xlsx", ".csv", ".zip", ".svg"]):
        return False
    return "/bulletins/" in path or "/articles/" in path


def extract_related_doc_urls(html):
    soup = BeautifulSoup(html, "html.parser")
    doc_urls = []
    containers = []
    containers.extend(soup.select("#related-links"))
    containers.extend(soup.select("[id*='related']"))
    if containers:
        for container in containers:
            for link in container.select("a[href]"):
                href = link.get("href")
                if is_document_link(href):
                    doc_urls.append(normalize_ons_path(href))
    if not doc_urls:
        for link in soup.select("a[href]"):
            href = link.get("href")
            if is_document_link(href):
                doc_urls.append(normalize_ons_path(href))
    return list(dict.fromkeys(doc_urls))


def extract_vis_urls(html):
    soup = BeautifulSoup(html, "html.parser")
    vis_urls = []
    for div in soup.select("div.pym-interactive[data-url]"):
        data_url = div.get("data-url")
        if not data_url:
            continue
        data_url = normalize_ons_path(data_url) or data_url.strip()
        if data_url:
            vis_urls.append(data_url)
    if not vis_urls:
        vis_urls = re.findall(r"/visualisations/[^\"\s]*", html)
    return list(dict.fromkeys(vis_urls))


def try_to_get_screenshot(filename, vis_url):
    "Returns True if no error was thrown"
    try:
        venv_bin = os.path.dirname(sys.executable)
        shot_scraper_exe = shutil.which("shot-scraper", path=venv_bin) or "shot-scraper"
        subprocess.run([
            shot_scraper_exe, make_ons_url(vis_url),
            '-o', 'screenshots/' + str(filename) + '.png',
            '--quality', '60', '--width', '960', '--wait', '4000',
            '--user-agent', 'jtrim.ons@gmail.com'
        ], check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as exc:
        print('Failed to screenshot', vis_url, '!')
        if exc.stderr:
            print('shot-scraper stderr:', exc.stderr.strip())
            if 'unexpected keyword argument \'devtools\'' in exc.stderr:
                print('Falling back to Playwright screenshot for', vis_url)
                return try_to_get_screenshot_with_playwright(filename, vis_url)
        return False


def try_to_get_screenshot_with_playwright(filename, vis_url):
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        print('Playwright import failed:', exc)
        return False
    target_url = make_ons_url(vis_url)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 960, "height": 720},
                user_agent='jtrim.ons@gmail.com'
            )
            page = context.new_page()
            page.goto(target_url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(4000)
            page.screenshot(path='screenshots/' + str(filename) + '.png', full_page=True)
            context.close()
            browser.close()
        return True
    except Exception as exc:
        print('Playwright screenshot failed for', target_url, ':', exc)
        return False

def process_doc(doc_uri, results, screenshot_filenames, most_recent_prev_release_date):
    doc_url = make_ons_url(doc_uri) if doc_uri.startswith("/") else doc_uri
    raw_doc_page = get_page(doc_url)
    if not raw_doc_page:
        print('PROBLEM PARSING', doc_url)
        return False
    soup = BeautifulSoup(raw_doc_page, "html.parser")
    title = extract_title(soup)
    release_date = extract_release_date(raw_doc_page)
    if not release_date:
        print('PROBLEM GETTING RELEASE DATE FOR', doc_url)
    else:
        print(release_date, title)
        is_old = compare_dates(release_date, most_recent_prev_release_date)
        if is_old is True:
            return True

    all_vis_urls = extract_vis_urls(raw_doc_page)
    for vis_url in all_vis_urls:
        print("   ", vis_url)
        if '.xls' in vis_url or '.pdf' in vis_url or '.svg' in vis_url:
            continue
        if (vis_url not in screenshot_filenames):
            filename = len(screenshot_filenames)
            if try_to_get_screenshot(filename, vis_url):
                screenshot_filenames[vis_url] = filename

    results.append({
        "title": title,
        "doc_uri": doc_url,
        "vis_urls": all_vis_urls,
        "release_date": release_date
    })
    if len(all_vis_urls) > 0:
        print('Got vizzes. Sleeping for 10 seconds.')
        time.sleep(10)
    return False


def display_page_number(page_num):
    print("****************")
    print("PAGE", page_num)
    print("****************")


def scrape_results(results, screenshot_filenames, most_recent_prev_release_date):
    LAST_PAGE = 15
    for page_num in range(1, LAST_PAGE + 1):
        display_page_number(page_num)
        lst = json.loads(get_page(PAGE_LIST_URL + str((page_num-1)*RESULT_SIZE)))
        for i, result in enumerate(lst["releases"]):
            print(i)
            release_url = make_ons_url(result["uri"])
            raw_page = get_page(release_url)
            if not raw_page:
                print('Failed to parse', release_url, '!')
                continue
            related_docs = extract_related_doc_urls(raw_page)

            if len(related_docs) == 0:
                continue

            done = True
            for doc_uri in related_docs:
                if not process_doc(doc_uri, results, screenshot_filenames, most_recent_prev_release_date):
                    # Only finish early if all documents are old.
                    # TODO: avoid the `done` variable... and tidy up all the code in this file!
                    done = False
            if done:
                print('Finishing early.')
                return


def main():
    with open('articles-and-dvcs.json', 'r') as f:
        results = json.load(f)
    with open('screenshot-filenames.json', 'r') as f:
        screenshot_filenames = json.load(f)

    normalized_release_dates = [
        normalize_release_date(result.get('release_date', ''))
        for result in results
        if result.get('release_date')
    ]
    most_recent_prev_release_date = max(normalized_release_dates) if normalized_release_dates else ''
    print(f'Most recent previous release date: {most_recent_prev_release_date}')

    scrape_results(results, screenshot_filenames, most_recent_prev_release_date)

    with open('articles-and-dvcs.json', 'w') as f:
        results_without_duplicates = [
            json.loads(s) for s in set(json.dumps(result, sort_keys=True) for result in results)
        ]
        json.dump(results_without_duplicates, f, indent=4)
    with open('screenshot-filenames.json', 'w') as f:
        json.dump(screenshot_filenames, f, indent=4)

if __name__ == "__main__":
    main()
