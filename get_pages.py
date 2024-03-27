import json
import re
import requests
import subprocess
import time
import random
import sys
from urllib.parse import urljoin

ONS_URL = "https://www.ons.gov.uk"
PAGE_LIST_URL = (
    ONS_URL + "/releasecalendar/data?fromDateDay=&fromDateMonth=&fromDateYear=" +
    "&query=&size=50&toDateDay=&toDateMonth=&toDateYear=&view=&page="
)

def make_ons_url(url_path):
    return urljoin(ONS_URL, url_path)

def make_data_url(url):
    if url.endswith('/'):
        return url + 'data'
    else:
        return url + '/data'

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


def try_to_get_screenshot(filename, vis_url):
    "Returns True if no error was thrown"
    try:
        subprocess.run([
            'shot-scraper', make_ons_url(vis_url),
            '-o', 'screenshots/' + str(filename) + '.png',
            '--quality', '60', '--width', '960', '--wait', '4000',
            '--user-agent', 'jtrim.ons@gmail.com'
        ], check=True)
        return True
    except:
        print('Failed to screenshot', vis_url, '!')
        return False

def process_doc(doc_uri, results, screenshot_filenames, most_recent_prev_release_date):
    raw_doc_page = get_page(make_data_url(doc_uri))
    try:
        doc_page = json.loads(raw_doc_page)
    except:
        print('PROBLEM PARSING', doc_uri)
        return False
    title = doc_page["description"]["title"]
    try:
        release_date = doc_page["description"]["releaseDate"]
    except KeyError:
        print('PROBLEM GETTING RELEASE DATE FOR', doc_uri)
        return False
    print(release_date, title)
    if release_date <= most_recent_prev_release_date:
        return True
    if "sections" not in doc_page:
        return False
    all_vis_urls = []
    for section in doc_page["sections"]:
        dvc_regex = r'/visualisations/dvc[^"\s]*'
        vis_urls = re.findall(dvc_regex, section["markdown"])
        for vis_url in vis_urls:
            print("   ", vis_url)
            if '.xls' in vis_url or '.pdf' in vis_url or '.svg' in vis_url:
                continue
            if (vis_url not in screenshot_filenames):
                filename = len(screenshot_filenames)
                if try_to_get_screenshot(filename, vis_url):
                    screenshot_filenames[vis_url] = filename

        all_vis_urls.extend(vis_urls)
    results.append({
        "title": title,
        "doc_uri": doc_uri,
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
        lst = json.loads(get_page(PAGE_LIST_URL + str(page_num)))
        for i, result in enumerate(lst["result"]["results"]):
            print(i)
            uri = make_data_url(make_ons_url(result["uri"]))
            raw_page = get_page(uri)
            try:
                page = json.loads(raw_page)
            except:
                print('Failed to parse', uri, '!')
                continue
            if "relatedDocuments" not in page:
                continue
            for doc in page["relatedDocuments"]:
                doc_uri = make_ons_url(doc["uri"])
                done = process_doc(doc_uri, results, screenshot_filenames, most_recent_prev_release_date)
                if done:
                    print('Finishing early.')
                    return


def main():
    with open('articles-and-dvcs.json', 'r') as f:
        results = json.load(f)
    with open('screenshot-filenames.json', 'r') as f:
        screenshot_filenames = json.load(f)

    most_recent_prev_release_date = max(
        result['release_date'] for result in results
    ) if len(results) else ''
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
