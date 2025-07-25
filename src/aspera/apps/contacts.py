"""The user's personal contact book."""

import datetime
from dataclasses import dataclass
from typing import Literal


@dataclass
class Address:

    street: str | None = None
    town_or_city: str | None = None
    country: str | None = None
    postal_code: str | None = None


@dataclass
class ContactAddress(Address):
    """
    Properties
    ----------
    address_identifier
        An optional label attached to the address. Use `str` to
        specify user custom labels.
    """

    address_identifier: Literal["home", "work", "school"] | str | None = None


class ContactEmail:
    value: str
    type: Literal["home", "work", "school"] | str | None = None


@dataclass
class Contact:
    """A contact stored on the user's device.

    Parameters
    ----------
    company
        The employer of the contact.
    addresses
        The user may have multiple addresses associated with this contact
        (eg both the home and work address of the contact).
    email
        Like for `addresses`, multiple labelled email addresses are
        associated with a contact.
    """

    first_name: str
    last_name: str
    mobile: int
    company: str | None = None
    birth_date: datetime.date | None = None
    addresses: list[ContactAddress] | None = None
    email: list[ContactEmail] | None = None


def add_custom_label_address(contact: Contact, address: Address, label: str) -> Contact:
    """Add an address with a user-specified custom label to a contact."""
    ...


class ContactsAPI:

    @staticmethod
    def search_contacts(query: str) -> list[Contact]:
        """Search contacts based on a query. The query is matched
        against `first_name` and `last_name` or `company` fields."""
        ...

    @staticmethod
    def remove_contact(contact: Contact):
        """Remove a contact from user's contact list."""
        ...
