"""A module implementing a simple search engine for user's device."""

import datetime
from dataclasses import dataclass
from typing import Literal

# documents and utilities for working with them


@dataclass
class Document:
    """A document on the user's device.

    Properties
    ----------
    folder
        By default, all documents are stored in the generic
        `InternalStorage` folder. Property should be updated
        for existing documents to move them to a new location.
    """

    title: str | None = None
    content: str | None = None
    author: list[str] | None = None
    num_pages: int | None = None
    last_modified: datetime.datetime | None = None
    created_on: datetime.datetime | None = None
    is_starred: bool = False
    folder: str = "InternalStorage"


def search_documents(
    title_query: str | None = None,
    date_created: datetime.date | None = None,
    content_query: str | None = None,
    author: str | None = None,
    last_modified: datetime.date | None = None,
    max_results: int | None = 1,
) -> list[Document]:
    """Search documents the user stored on their device, according to one or
    more criteria. To return all documents, use
    `search_documents(max_results=None)`."""


def search_in_document(phrase: str, document: Document) -> bool:
    """Check whether the phrase is present in `Document`. This is
    a typical find function, using exact match at the character level."""


def delete_document(document: Document):
    """Delete an existing document."""


def print_docs(docs: list[Document]):
    """Print a list of documents. Will be sent to the nearest printer."""


def backup(
    docs: list[Document], provider: Literal["gdrive", "icloud", "onedrive"] = "icloud"
):
    """Backup documents to the cloud."""


def rename_document(document: Document):
    """Rename a document in-place."""


# photos and utilities for working with them
