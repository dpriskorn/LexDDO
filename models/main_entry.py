import json
from typing import List

from models.enums import LexicalCategory


class MainEntry:
    labels: List
    # This id is found in the list we scrape
    select_id: str
    # Entry id is unique and only found on the page of the entry, not in the list we scrape
    entry_id: int
    lexical_category: LexicalCategory
    # each definition also has an id but we don't support that yet
    # definitions: List

    def __init__(
        self, select_id: str = None, labels: List = None, lexical_category: str = None
    ):
        self.select_id = select_id
        self.labels = labels
        self.lexical_category = LexicalCategory(lexical_category)

    def json(self):
        return json.dumps(
            dict(
                select_id=self.select_id,
                labels=self.labels,
                lexical_category=self.lexical_category.name,
            )
        )

    def url(self):
        return f"https://ordnet.dk/ddo/ordbog?aselect={self.id}&query=wd"
