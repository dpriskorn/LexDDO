# Press Skift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
#!/usr/bin/env python3
# author: Dennis Priskorn 2021
# based on https://gist.github.com/salgo60/73dc99d71fcdeb75e4d69bd73b71acf9 which was
# based on https://github.com/Torbacka/wordlist/blob/master/client.py
import logging
import re
from urllib.parse import parse_qs
from datetime import datetime
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.DEBUG)

headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:63.0) Gecko/20100101 Firefox/63.0'
}
date = datetime.today().strftime("%Y-%m-%d")
print(date)
file = open(f"ddo_{date}.csv", "a")


def fetch_and_parse(url):
    logger = logging.getLogger(__name__)
    logger.info(f"Fetching:{url}")
    response = requests.get(url, headers=headers)
    return parse_response(response)


def main():
    logger = logging.getLogger(__name__)
    next_page_url, first_id = fetch_and_parse("https://ordnet.dk/ddo/ordbog?query=a")
    while True:
        if first_id >= 354:
            next_page_url, first_id = fetch_and_parse(next_page_url)
        else:
            logger.info("Done")
            break


# Parse the html response from ordnet.dk
def parse_response(response: requests.Response):
    logger = logging.getLogger(__name__)
    if response is None:
        raise ValueError("Response was None")
    soup = BeautifulSoup(response.text, features="html.parser")
    box = soup.find("div", {"class": "searchResultBox"})
    divs = box.findAll("div")
    # logger.debug(f"links:{divs}")
    logger.info(f"{len(divs)} entries found")
    if len(divs) == 0:
        return None
    for div in divs:
        gather_information(div)
    # looks like this: https://ordnet.dk/ddo/ordbog?browse=down&last_id=394&first_id=354&query=a&aselect=A,1
    next_page_div = soup.find("div", {"class": "rulNed"})
    next_page_string = next_page_div.find("a")["href"]
    logger.debug(f"url:{next_page_string}")
    next_page_url = parse_qs(next_page_string)
    first_id: int = int(next_page_url['first_id'][0])
    #logger.debug(next_page_url)
    #logger.debug(f"first_id:{first_id}")
    return next_page_string, first_id


def gather_information(div):
    """Gather information from soup object"""
    logger = logging.getLogger(__name__)
    logger.debug(f"div:{div}")
    lexical_category = div.text
    link = div.find("a")
    labels_string = link.text
    logger.debug(f"labels:{labels_string}")
    labels = []
    if " eller " in labels_string:
        labels_raw = labels_string.strip().split(" eller ")
        for label in labels_raw:
            # remove numbers
            labels.append(re.sub('[0-9]$', '', label))
        logger.debug(f"multiple labels:{labels}")
        #raise ValueError("Multiple labels not supported yet")
    else:
        labels.append(labels_string)
    url_string = link["href"]
    if url_string is None:
        raise ValueError("Could not find url")
    else:
        url = parse_qs(url_string)
        logger.debug(f"url:{url}")
        print(url.keys())
        exit(0)
        #select_id = url['select']
        #logger.debug(f"url:{url_string}, {select_id}")

    # span = div.findAll('span')
    # file.write(span[0].getText().strip() +
    #            "," + span[1].getText().strip() +
    #            "," + span[2].getText().strip() +
    #            "," + span[3].getText().strip() +
    #            "," + div['href'].strip() + "\n")


if __name__ == '__main__':
    main()
