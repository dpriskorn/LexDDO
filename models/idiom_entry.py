from typing import List


class IdiomEntry:
    labels: List
    # Idioms only have numeric ids
    id: int

    def __init__(self, id: int = None, labels: List = None):
        self.id = id
        self.labels = labels

    def url(self):
        return f"https://ordnet.dk/ddo/ordbog?mselect={self.id}&query=wd"
