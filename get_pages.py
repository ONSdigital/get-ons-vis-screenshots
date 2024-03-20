import json
import re
import requests
import subprocess
import time

ONS_URL = "https://www.ons.gov.uk/"
PAGE_LIST_URL = (
    ONS_URL + "/releasecalendar/data?fromDateDay=&fromDateMonth=&fromDateYear=" +
    "&query=&size=50&toDateDay=&toDateMonth=&toDateYear=&view=&page="
)

def get_page(url):
    print("***", url)
    content = requests.get(url).text
    time.sleep(1)
    return content


def process_doc(doc_uri, results, screenshot_filenames, vis_seen_before_counter):
    raw_doc_page = get_page(doc_uri + "/data")
    try:
        doc_page = json.loads(raw_doc_page)
    except:
        print('PROBLEM PARSING', doc_uri)
        return
    title = doc_page["description"]["title"]
    try:
        summary = doc_page["description"]["summary"]
    except KeyError:
        summary = ""
    try:
        release_date = doc_page["description"]["releaseDate"]
    except KeyError:
        release_date = ""
    print(title)
    print(doc_uri)
    if "sections" in doc_page:
        all_vis_urls = []
        for section in doc_page["sections"]:
            dvc_regex = r'/visualisations/dvc[^"\s]*'
            vis_urls = re.findall(dvc_regex, section["markdown"])
            for vis_url in vis_urls:
                print("   ", vis_url)
                if '.xls' in vis_url or '.pdf' in vis_url:
                    continue
                if (vis_url in screenshot_filenames):
                    vis_seen_before_counter[0] += 1
                else:
                    vis_seen_before_counter[0] = 0
                    filename = len(screenshot_filenames)
                    try:
                        subprocess.run([
                            'shot-scraper', ONS_URL + vis_url,
                            '-o', 'screenshots/' + str(filename) + '.png',
                            '--quality', '60', '--wait', '4000'
                        ])
                        screenshot_filenames[vis_url] = filename
                    except:
                        print('Failed to screenshot', vis_url, '!')
                        pass

            all_vis_urls.extend(vis_urls)
        if len(all_vis_urls) > 0:
            results.append({
                "title": title,
                "doc_uri": doc_uri,
                "vis_urls": all_vis_urls,
                "summary": summary,
                "release_date": release_date
            })


def display_page_number(page_num):
    for i in range(3):
        print("****************")
    print("PAGE", page_num)
    for i in range(3):
        print("****************")


def main():
    with open('articles-and-dvcs.json', 'r') as f:
        results = json.load(f)
    with open('screenshot-filenames.json', 'r') as f:
        screenshot_filenames = json.load(f)

    # When we've seen 20 vizzes in a row before, stop.
    vis_seen_before_counter = [0]

    LAST_PAGE = 1
    for page_num in range(1, LAST_PAGE + 1):
        if vis_seen_before_counter[0] >= 20:
            break
        display_page_number(page_num)
        lst = json.loads(get_page(PAGE_LIST_URL + str(page_num)))
        for result in lst["result"]["results"]:
            if vis_seen_before_counter[0] >= 20:
                break
            uri = ONS_URL + result["uri"] + "/data"
            raw_page = get_page(uri)
            try:
                page = json.loads(raw_page)
            except:
                print('Failed to parse', uri, '!')
                continue
            if "relatedDocuments" not in page:
                continue
            for doc in page["relatedDocuments"]:
                doc_uri = ONS_URL + doc["uri"]
                process_doc(doc_uri, results, screenshot_filenames, vis_seen_before_counter)

        # Save to file after every page of results, so we'll have some results
        # even if the program crashes eventually :-)
        with open('articles-and-dvcs.json', 'w') as f:
            json.dump(results, f, indent=4)
        with open('screenshot-filenames.json', 'w') as f:
            json.dump(screenshot_filenames, f, indent=4)

    if vis_seen_before_counter[0] >= 20:
        print('Finished early, because 20 vizzes in a row have been scraped already.')

if __name__ == "__main__":
    main()
