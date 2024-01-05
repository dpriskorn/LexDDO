import logging
from typing import List, Dict

import requests
from bs4 import BeautifulSoup, SoupStrainer
from pydantic import BaseModel
from requests import Session
from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.datatypes import ExternalID, Item, Time
from wikibaseintegrator.entities import LexemeEntity
from wikibaseintegrator.models import Qualifiers
from wikibaseintegrator.wbi_config import config as wbconfig
from wikibaseintegrator.wbi_helpers import execute_sparql_query
from wikibaseintegrator.wbi_login import Login
from urllib.parse import quote

import config

logging.basicConfig(level=config.loglevel)
logger = logging.getLogger(__name__)
wbconfig["USER_AGENT"] = config.user_agent


class OrdnetError(BaseException):
    pass


class DdoMatcher(BaseModel):
    lids: List[str] = list()
    lexical_categories: Dict[str, str] = dict(
        adverbium="Q380057",
        substantiv="Q1084",
        adjektiv="Q34698",
        udråbsord="Q83034",
        verbum="Q24905",
        konjunktion="Q36484",
        suffiks="Q102047",
        præfiks="Q134830",
        talord="Q63116"
    )
    session: Session = requests.Session()

    class Config:
        arbitrary_types_allowed = True

    def download_lids(self):
        query = """
        SELECT ?lexeme WHERE {
            ?lexeme dct:language wd:Q9035;
                    wikibase:lemma ?lemma.
            FILTER NOT EXISTS {
                ?lexeme wdt:P9529 [].
                }
            FILTER NOT EXISTS {
                ?lexeme wdt:P9530 [].
            }
        }
        offset 100
        limit 100
        """
        result = execute_sparql_query(query=query)
        self.lids = [
            item["lexeme"]["value"].replace("http://www.wikidata.org/entity/", "")
            for item in result["results"]["bindings"]
        ]

    def find_lexical_category_qid(self, response) -> str:
        from bs4 import SoupStrainer

        only_div_tags = SoupStrainer("div")
        soup = BeautifulSoup(response.text, "lxml", parse_only=only_div_tags)
        # Find the first div element with class 'definitionBoxTop'
        first_definition_box_top_div = soup.find(
            "div", class_="definitionBoxTop"
        )

        # Find the first span with class 'highlightedGlossaryTerm' inside the first definitionBoxTop
        if first_definition_box_top_div:
            logger.debug(first_definition_box_top_div)
            # exit()
            textmedium_span = first_definition_box_top_div.find(
                "span", class_="tekstmedium"
            )
            if textmedium_span:
                lexical_category = (
                    textmedium_span.get_text().split()[0].replace(",", "")
                )
                logger.debug("Found span in first div:", lexical_category)
                if lexical_category in self.lexical_categories:
                    qid = self.lexical_categories.get(lexical_category)
                    logger.debug(
                        f"found {qid}"
                    )
                    return qid
                else:
                    raise ValueError(f"did not recognize lexcat {lexical_category}")
            else:
                raise ValueError(
                    "No span with class 'tekstmedium' found in the first div"
                )
        else:
            raise ValueError("No div with class 'definitionBoxTop' found.")

    @staticmethod
    def is_single_hit_in_ddo(response) -> bool:
        from bs4 import SoupStrainer

        only_div_tags = SoupStrainer("div")
        soup = BeautifulSoup(response.text, "lxml", parse_only=only_div_tags)
        # Select the first div with class 'diskret'
        first_diskret_div = soup.find('div', class_='diskret')

        # Get the text content inside the first div
        if first_diskret_div:
            text_inside_first_div = first_diskret_div.get_text()
            logger.debug(text_inside_first_div)
            if text_inside_first_div.strip() == "(1)":
                logger.debug("Content of the div is '(1)'")
                # todo add the id of this entry to wikidata
                return True
            else:
                logger.debug("Content of the div is not '(1)'")
                return False
        else:
            raise ValueError("No div with class 'diskret' found.")

    @staticmethod
    def get_match_url(response):
        from bs4 import SoupStrainer

        only_a_tags = SoupStrainer("a")
        soup = BeautifulSoup(response.text, "lxml", parse_only=only_a_tags)
        # Find the first anchor element with class 'searchMatch'
        return soup.find('a', class_='searchMatch')

    @staticmethod
    def get_ddo_article_id(response) -> str:
        from bs4 import SoupStrainer

        only_a_tags = SoupStrainer("a")
        soup = BeautifulSoup(response.text, "lxml", parse_only=only_a_tags)
        # Find the first anchor element with class 'searchMatch'
        # Find the anchor element with class 'fejlrapport'
        anchor = soup.find('a', class_='fejlrapport')

        # Extract the value of the href attribute
        if anchor:
            href_value = anchor.get('href')
            logger.debug(href_value)
            return href_value.split("(")[1].rstrip(")")
        else:
            raise ValueError("Anchor element not found.")

    @staticmethod
    def number_of_lexemes_with_identical_lemma_and_lexcat(lemma, lexcat) -> int:
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
        logger.info(f"Found {count} lexemes with the same lemma and category in WD")
        return count

    @staticmethod
    def get_ddo_lemma(response) -> str:
        # Create a custom soup strainer to filter elements by class
        strainer = SoupStrainer(class_="match")

        # Parse only the parts of the document that match the strainer
        soup = BeautifulSoup(response.text, 'lxml', parse_only=strainer)

        # Find the span element with the class 'match' and extract its text
        span_match = soup.find('span', class_='match')
        logger.debug(span_match)
        if span_match:
            # Remove any span elements with the class 'super' inside the 'match' span
            for span_super in span_match.find_all('span', class_='super'):
                span_super.decompose()
            text = span_match.get_text()
            logger.debug(text)
            return text
        else:
            raise ValueError("Element with class 'match' not found")

    @staticmethod
    def enrich_wikidata(lexeme: LexemeEntity, ):
        # print(lexeme.get_entity_url())
        # pprint(self.item.get_json())
        if config.press_enter_to_continue:
            input("press enter to upload")
        lexeme.write(
            summary="Adding DDO identifier with [[Wikidata:Tools/LexDDO|LexDDO]]"
        )
        print(lexeme.get_entity_url())
        # if config.press_enter_to_continue:
        #     input("press enter to continue")

    @staticmethod
    def remove_not_found_in_ddo_if_present(lexeme):
        try:
            not_found_in = lexeme.claims.get(property="P9660")
            for claim in not_found_in:
                logger.debug(claim.mainsnak.datavalue)
                #exit()
                if claim.mainsnak.datavalue["value"]["id"] == "Q1186741":
                    claim.remove()
                    print("Removed not found in -> DDO statement")
                    input("press enter to continue")
            # This should cause the claim to be removed
        except KeyError:
            pass
        return lexeme

    def lookup_labels(self):
        wbi = WikibaseIntegrator(
            login=Login(user=config.user_name, password=config.bot_password)
        )
        for lid in self.lids:
            lexeme = wbi.lexeme.get(lid)
            lemma = lexeme.lemmas.get(language="da")
            if not lemma:
                raise ValueError("no danish lemma for this danish lexeme")
            else:
                print(f"Working on '{lemma}'")
                # Adding the lookup to ordnet.dk
                ordnet_url = (
                    f"https://ordnet.dk/ddo/quick_search?SearchableText={quote(string=str(lemma))}"
                )
                response = self.session.get(ordnet_url)
                if response.status_code == 200:
                    ddo_lemma = self.get_ddo_lemma(response=response)
                    if lemma != ddo_lemma:
                        logger.warning(f"lemmas do not match, got lemma {ddo_lemma} from DDO. "
                                       f"These are often near matches, we skip them for now "
                                       f"because we have not decided how to handle these yet. Skipping.")
                        continue
                    # print(f"Ordnet.dk response for {lemma}:")
                    logger.info(ordnet_url)
                    if self.is_single_hit_in_ddo(response=response):
                        qid = self.find_lexical_category_qid(response=response)
                        if qid and qid == lexeme.lexical_category:
                            count = self.number_of_lexemes_with_identical_lemma_and_lexcat(lemma=lemma, lexcat=qid)
                            if count == 1:
                                # check match url if idiom
                                match_url = self.get_match_url(response)
                                logger.debug(match_url)
                                if "mselect" not in match_url:
                                    ddo_article_id = self.get_ddo_article_id(response)
                                    print(ddo_article_id)
                                    ddo_claim = ExternalID(
                                        prop_nr="P9529",
                                        value=ddo_article_id
                                    )
                                    lexeme.add_claims(claims=[ddo_claim])
                                    lexeme = self.remove_not_found_in_ddo_if_present(lexeme)
                                    self.enrich_wikidata(lexeme=lexeme)
                                    # exit()
                                else:
                                    logger.info("Idiom detected")
                                    mselect_start = match_url.find("mselect=")
                                    if mselect_start != -1:
                                        mselect_start += len("mselect=")
                                        mselect_end = match_url.find("&", mselect_start)
                                        if mselect_end == -1:
                                            mselect_end = len(match_url)
                                        ddo_idiom_id = match_url[mselect_start:mselect_end]
                                        print(f"mselect value: {ddo_idiom_id}")
                                        ddo_claim = ExternalID(
                                            prop_nr="P9530",
                                            value=ddo_idiom_id
                                        )
                                        lexeme.add_claims(claims=[ddo_claim])
                                        lexeme = self.remove_not_found_in_ddo_if_present(lexeme)
                                        self.enrich_wikidata(lexeme=lexeme)
                                    else:
                                        raise ValueError("mselect value not found in the URL")
                            # sleep(1)
                            else:
                                print("We don't support matching on lexemes where "
                                      "multiple exists with identical lemma and lexical category")
                        else:
                            print(f"Lexical categories do not match, see {ordnet_url} and {lexeme.get_entity_url()}, skipping")
                            input("press enter to continue")
                    else:
                        logger.info(f"Not a single hit in DDO, see {ordnet_url}. We don't support these yet, skipping.")
                else:
                    if response.status_code == 404:
                        print("Got 404 from DDO, adding not found in statement")
                        # DDO is a moving target so we add point in time to this
                        time = Time(
                            prop_nr="P585",
                            time="now",
                            precision=11
                        )
                        not_found_in_ddo = Item(
                            prop_nr="P9660",
                            value="Q1186741",
                            qualifiers=Qualifiers().add(qualifier=time)
                        )
                        lexeme.add_claims(claims=[not_found_in_ddo])
                        self.enrich_wikidata(lexeme=lexeme)
                        input("press enter to continue")
                    else:
                        raise OrdnetError(f"Error accessing ordnet.dk for {lemma}, see {ordnet_url}")


ddo = DdoMatcher()
ddo.download_lids()
print(ddo.lids)
ddo.lookup_labels()
