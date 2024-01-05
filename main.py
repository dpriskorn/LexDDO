from typing import List, Dict
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel
from requests import Session
from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.wbi_helpers import execute_sparql_query
from time import sleep

class DdoMatcher(BaseModel):
    lids: List[str] = list()
    lexical_categories: Dict[str, str] = dict(
        adverbium="Q380057",
        substantiv="Q1084",
        adjektiv="Q34698",
        udråbsord="Q83034",
        verbum="Q24905",
    )
    session: Session = requests.Session()

    class Config:
        arbitrary_types_allowed = True

    def download_lids(self):
        url = "https://query.wikidata.org/sparql"
        query = """
        SELECT ?lexeme WHERE {
            ?lexeme dct:language wd:Q9035;
                    wikibase:lemma ?lemma.
            FILTER NOT EXISTS {
                ?lexeme wdt:P9529 [].
                ?lexeme wdt:P9530 [].
            }
        }
        limit 10
        """
        result = execute_sparql_query(query=query)
        self.lids = [
            item["lexeme"]["value"].replace("http://www.wikidata.org/entity/", "")
            for item in result["results"]["bindings"]
        ]

    def find_lexical_category_qid(self, response) -> str:
        # Parse the HTML content
        soup = BeautifulSoup(response.text, "lxml")
        # Find the first div element with class 'definitionBoxTop'
        first_definition_box_top_div = soup.find(
            "div", class_="definitionBoxTop"
        )

        # Find the first span with class 'highlightedGlossaryTerm' inside the first definitionBoxTop
        if first_definition_box_top_div:
            print(first_definition_box_top_div)
            # exit()
            textmedium_span = first_definition_box_top_div.find(
                "span", class_="tekstmedium"
            )
            if textmedium_span:
                lexical_category = (
                    textmedium_span.get_text().split()[0].replace(",", "")
                )
                print("Found span in first div:", lexical_category)
                if lexical_category in self.lexical_categories:
                    qid = self.lexical_categories.get(lexical_category)
                    print(
                        f"found {qid}"
                    )
                    return qid
                else:
                    print(f"did not recognize lexcat {lexical_category}")
                    exit()
            else:
                print(
                    "No span with class 'highlightedGlossaryTerm' found in the first div"
                )
        else:
            print("No div with class 'definitionBoxTop' found.")

    def is_single_hit_in_ddo(self, response) -> bool:
        soup = BeautifulSoup(response.text, "lxml")
        # Select the first div with class 'diskret'
        first_diskret_div = soup.find('div', class_='diskret')

        # Get the text content inside the first div
        if first_diskret_div:
            text_inside_first_div = first_diskret_div.get_text()
            print(text_inside_first_div)
            if text_inside_first_div.strip() == "(1)":
                print("Content of the div is '(1)'")
                # todo add the id of this entry to wikidata
                return True
            else:
                print("Content of the div is not '(1)'")
                return False
        else:
            print("No div with class 'diskret' found.")

    def get_match_url(self, response):
        from bs4 import SoupStrainer

        only_a_tags = SoupStrainer("a")
        soup = BeautifulSoup(response.text, "lxml", parse_only=only_a_tags)
        # Find the first anchor element with class 'searchMatch'
        return soup.find('a', class_='searchMatch')

    def get_ddo_article_id(self, response) -> str:
        from bs4 import SoupStrainer

        only_a_tags = SoupStrainer("a")
        soup = BeautifulSoup(response.text, "lxml", parse_only=only_a_tags)
        # Find the first anchor element with class 'searchMatch'
        # Find the anchor element with class 'fejlrapport'
        anchor = soup.find('a', class_='fejlrapport')

        # Extract the value of the href attribute
        if anchor:
            href_value = anchor.get('href')
            print(href_value)
            return href_value.split("(")[1].rstrip(")")
        else:
            raise ValueError("Anchor element not found.")

    def number_of_lexemes_with_identical_lemma_and_lexcat(self, lemma, lexcat) -> int:
        # todo check if multiple lexemes with this lemma and lexical category in WD
        query = f"""
            SELECT (COUNT(?lexeme) as ?count) WHERE {{
                ?lexeme dct:language wd:Q9035;
                        wikibase:lemma "{lemma}"@da;
                        wikibase:lexicalCategory wd:{lexcat}.
            }}
        """
        data = execute_sparql_query(query)
        count = int(data['results']['bindings'][0]['count']['value'])
        print(f"Found {count} lexemes with the same lemma and category in WD")
        return count

    def lookup_labels(self):
        wbi = WikibaseIntegrator()
        for lid in self.lids:
            lexeme = wbi.lexeme.get(lid)
            lemma = lexeme.lemmas.get(language="da")
            if lemma:
                print(lemma)
                # Adding the lookup to ordnet.dk
                ordnet_url = (
                    f"https://ordnet.dk/ddo/quick_search?SearchableText={lemma}"
                )
                response = self.session.get(ordnet_url)
                if response.status_code == 200:
                    print(f"Ordnet.dk response for {lemma}:")
                    print(ordnet_url)
                    if self.is_single_hit_in_ddo(response=response):
                        qid = self.find_lexical_category_qid(response=response)
                        if qid:
                            if qid == lexeme.lexical_category:
                                count = self.number_of_lexemes_with_identical_lemma_and_lexcat(lemma=lemma, lexcat=qid)
                                if count == 1:
                                    # check match url if idiom
                                    match_url = self.get_match_url(response)
                                    print(match_url)
                                    if "mselect" not in match_url:
                                        ddo_article_id = self.get_ddo_article_id(response)
                                        print(ddo_article_id)
                                        sleep(1)
                                        # exit()
                                    else:
                                        # todo parse match_url using regex from WD
                                        mselect_start = match_url.find("mselect=")
                                        if mselect_start != -1:
                                            mselect_start += len("mselect=")
                                            mselect_end = match_url.find("&", mselect_start)
                                            if mselect_end == -1:
                                                mselect_end = len(match_url)
                                            mselect_value = match_url[mselect_start:mselect_end]
                                            print(f"mselect value: {mselect_value}")
                                            sleep(1)
                                            # exit()
                                        else:
                                            raise ValueError("mselect value not found in the URL")
                                    # todo upload ddo statement
                                # sleep(1)
                                else:
                                    print("We don't support matching on lexemes where "
                                          "multiple exists with identical lemma and lexical category")

                else:
                    print(f"Error accessing ordnet.dk for {lemma}")


ddo = DdoMatcher()
ddo.download_lids()
print(ddo.lids)
ddo.lookup_labels()
