"""
The need for this class is due to the complex responses that
Census Reporter gives, this makes that interface much cleaner
without having to parse / rearrange the response.


The _inner_dict for the namespace has the following
structure:

{
    "B01001": {
        "estimate": {
            "B01001001": 1000,
            "B01001002": 1000,
            ... more estimates
        },
        "error": {
            "B01001001": 10,
            "B01001001": 10,
            ... more errors
        },
    },
    ... more tables
}


Ideally, we'd be able to eventually make a more sensible response
and then we could remove this code.
"""

from dataclasses import dataclass
from .datatypes import Estimate


@dataclass
class Namespace:
    """
    This class makes pulling a variable and placing it into an 
    'Estimate' from the complex CR api response as simple as calling
    a dictionary.
    """
    _inner_dict: dict

    def __getitem__(self, key: str) -> Estimate:
        table_name = key[:-3]
        return Estimate(
            self._inner_dict[table_name]["estimate"][key],
            self._inner_dict[table_name]["error"][key]
        )

    def __contains__(self, key: str) -> bool:
        table_name = key[:-3]
        return key in self._inner_dict[table_name]["estimate"]


