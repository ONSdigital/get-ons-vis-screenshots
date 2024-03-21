import json
import re
import requests
import subprocess
import time
import random
import sys

ONS_URL = "https://www.ons.gov.uk"
PAGE_LIST_URL = (
    ONS_URL + "/releasecalendar/data?fromDateDay=&fromDateMonth=&fromDateYear=" +
    "&query=&size=50&toDateDay=&toDateMonth=&toDateYear=&view=&page="
)

def make_ons_url(url_suffix):
    if not url_suffix.startswith('/'):
        url_suffix = '/' + url_suffix
    return ONS_URL + url_suffix

def get_page(url):
    time.sleep(1.5 + random.random())
    NUM_ATTEMPTS = 11
    for attempt_num in range(NUM_ATTEMPTS):
        print("***", url)
        response = requests.get(url)
        if response.status_code == 200:
            return response.text
        print("Status code", response.status_code, "for", url)
        if attempt_num < NUM_ATTEMPTS - 1:
            sleep_time = attempt_num * attempt_num + 2
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
            '--quality', '60', '--wait', '4000',
            '--user-agent', 'jtrim.ons@gmail.com'
        ], check=True)
        return True
    except:
        print('Failed to screenshot', vis_url, '!')
        return False

def process_doc(doc_uri, results, screenshot_filenames, vis_seen_before_counter):
    # Annoyingly, the /data pages for articles seem to give more rate limiting errors,
    # so get stuff from the HTML
    doc_page = get_page(doc_uri).splitlines()
    if len(doc_page) < 10:
        print('PROBLEM PARSING', doc_uri)
        return
    title = "UNKNOWN TITLE"
    for line in doc_page[:10]:
        if '<title>' in line:
            title = line.replace('<title>', '').replace('/<title>', '')
    release_date = 'UNKNOWN DATE'
    for line in doc_page[:100]:
        if 'releaseDate' in line:
            m = re.search('[0-9]{4}/[0-9]{2}/[0-9]{2}', line)
            if m:
                release_date = m.group()
            break
    print(title, release_date)
    print(doc_uri)

    # Regex starts with " to avoid getting the embed codes
    dvc_regex = r'"/visualisations/dvc[^"\s]*'
    all_vis_urls = []
    for line in doc_page:
        vis_urls = re.findall(dvc_regex, line)
        for vis_url in vis_urls:
            vis_url = vis_url[1:]  # Remove the leading "
            print("   ", vis_url)
            if '.xls' in vis_url or '.pdf' in vis_url or '.svg' in vis_url:
                continue
            if (vis_url in screenshot_filenames):
                vis_seen_before_counter[0] += 1
            else:
                vis_seen_before_counter[0] = 0
                filename = len(screenshot_filenames)
                if try_to_get_screenshot(filename, vis_url):
                    screenshot_filenames[vis_url] = filename
        all_vis_urls.extend(vis_urls)

    if len(all_vis_urls) > 0:
        results.append({
            "title": title,
            "doc_uri": doc_uri,
            "vis_urls": all_vis_urls,
            "release_date": release_date
        })
        print('Got vizzes. Sleeping for 61 seconds.')
        time.sleep(61)


def display_page_number(page_num):
    for i in range(3):
        print("****************")
    print("PAGE", page_num)
    for i in range(3):
        print("****************")


def main():
    print("Doing nothing for now.")
    sys.exit(0)
    with open('articles-and-dvcs.json', 'r') as f:
        results = json.load(f)
    with open('screenshot-filenames.json', 'r') as f:
        screenshot_filenames = json.load(f)

    # When we've seen 20 vizzes in a row before, stop.
    vis_seen_before_counter = [0]

    LAST_PAGE = 3
    for page_num in range(1, LAST_PAGE + 1):
        if vis_seen_before_counter[0] >= 20:
            break
        display_page_number(page_num)
        lst = json.loads(get_page(PAGE_LIST_URL + str(page_num)))
        for result in lst["result"]["results"]:
            if vis_seen_before_counter[0] >= 20:
                break
            uri = make_ons_url(result["uri"] + "/data")
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
                process_doc(doc_uri, results, screenshot_filenames, vis_seen_before_counter)

        # Save to file after every page of results, so we'll have some results
        # even if the program crashes eventually :-)
        with open('articles-and-dvcs.json', 'w') as f:
            results_without_duplicates = [
                json.loads(s) for s in set(json.dumps(result, sort_keys=True) for result in results)
            ]
            json.dump(results_without_duplicates, f, indent=4)
        with open('screenshot-filenames.json', 'w') as f:
            json.dump(screenshot_filenames, f, indent=4)

    if vis_seen_before_counter[0] >= 20:
        print('Finished early, because 20 vizzes in a row have been scraped already.')

if __name__ == "__main__":
    main()
