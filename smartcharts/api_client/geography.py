"""
Geography

This is the ugliest part of the code rn.

This module contains the geography object, which has a nice 
wrapper to the object returned by the Census Reporter API, 
avoiding storing derivable data, and hopefully providing 
opportunities for refactoring the API in the future.

This is living in the API folder for now, becuase that's mainly
where it's used, but it could prove to be useful elsewhere and 
can graduate out from there.
"""

from typing import Optional, Union, Any
from dataclasses import dataclass, field, asdict
from itertools import groupby

GeoID = str


SUMMARY_LEVELS = {
    "040": "state",
    "310": "msa",
    "050": "county",
    "060": "county_subdivision",
    "160": "place",
    "140": "tract",
    "150": "block_group",
    "500": "congressional_district",
    "610": "state_senate_district",
    "620": "state_house_district",
    "860": "zcta",
    "950": "elementary_school_district",
    "960": "high_school_district",
    "970": "unified_school_district",
}

sum_level_priority = {
    level: integer
    for integer, level in enumerate(SUMMARY_LEVELS.keys())
}


@dataclass
class Geography:
    full_name: str
    full_geoid: str
    short_name: Optional[str] = None
    land_area: Optional[int] = None
    awater: Optional[int] = None
    total_population: Optional[int] = None
    parents: list['Geography'] = field(default_factory=list)
    coverage: float = 100.0
    root: bool = False

    @property
    def short_geoid(self):
        _, short_geoid = self.full_geoid.split("US")

        return short_geoid

    @property
    def sumlevel(self):
        return self.full_geoid[:3]

    @property
    def sumlevel_name(self):
        return SUMMARY_LEVELS[self.sumlevel]

    @property
    def square_miles(self) -> float:
        """
        2589988 is square meters to square miles.
        """
        return self.land_area / 2589988

    @property
    def population_density(self) -> float:
        """
        This is probably going to need a zero division protection.
        """
        return self.total_population / self.square_miles

    @property
    def display_name(self) -> str:
        return self.full_name

    @property
    def simple_name(self) -> str:
        return self.short_name

    @property
    def population(self) -> int:
        return self.total_population

    @property
    def primary_parent(self) -> Union['Geography', None]:
        """
        This is the parent that has the most coverage over the node.

        Despite this being an iteration that could be time_consuming in theory,
        an object should at most have 3-4 parents, if that. So it makes more 
        sense to me to leave as a property.
        """
        if not self.parents:
            return None

        return max(self.parents, key=lambda parent: parent.coverage)

    def find_matriarch(self) -> 'Geography':
        """
        Find the parent at the broadest summary level.
        """
        if not self.parents:
            return self

        return self.primary_parent.find_matriarch()

    def show_lineage(self) -> list[str]:
        if not self.parents:
            return [self.full_geoid]
        elif self.sumlevel == "310":
            # This filter might expand depending on what the API returns.
            return self.primary_parent.show_lineage()
        return [self.full_geoid] + self.primary_parent.show_lineage()
    
    def show_detailed_lineage(self) -> list[dict[str, str]]:
        if not self.parents:
            return [{
                "relation": "this" if self.root else SUMMARY_LEVELS[self.sumlevel],
                "geoid": self.full_geoid,
            }]
        elif self.sumlevel == "310":
            # This filter might expand depending on what the API returns.
            return self.primary_parent.show_detailed_lineage()
        return [{
            "relation": "this" if self.root else SUMMARY_LEVELS[self.sumlevel],
            "geoid": self.full_geoid,
        }] + self.primary_parent.show_detailed_lineage()

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Trying to make the metadata and regular geography objects
        interchangable.
        """
        aliases = {
            "population": "total_population",
            "simple_name": "short_name",
            "display_name": "full_name",
            "aland": "land_area",
        }

        self.__dict__[aliases.get(name, name)] = value

    def full_lineage_wrap_up(self):
        if self.primary_parent is None:
            return {}
        return {
            self.primary_parent.sumlevel_name: self.primary_parent.wrap_up(bottom=False),
            **self.primary_parent.full_lineage_wrap_up()
        }

    def wrap_up(self, bottom=True):
        """
        This method is written out explicitly to avoid the recursive
        parent wrap up because the template expects it to be flat.
        """

        if bottom == True:
            parents = self.full_lineage_wrap_up()
            population_density = self.population_density
            square_miles = self.square_miles
            comparatives = [
                parent["this"]["sumlevel_name"] 
                for parent in parents.values()
            ]
        else:
            parents = None
            population_density = None
            square_miles = None
            comparatives = None

        return {
            "this": {
                "full_name": self.full_name,
                "full_geoid": self.full_geoid,
                "short_name": self.short_name,
                "land_area": self.land_area,
                "awater": self.awater,
                "total_population": self.total_population,
                "coverage": self.coverage,
                "root": self.root,
                "population": self.population,
                "population_density": population_density,
                "display_name": self.display_name,
                "short_geoid": self.short_geoid,
                "square_miles": square_miles,
                "sumlevel": self.sumlevel,
                "simple_name": self.simple_name,
                "sumlevel_name": self.sumlevel_name,
            },
            "full_name": self.full_name,
            "full_geoid": self.full_geoid,
            "short_name": self.short_name,
            "land_area": self.land_area,
            "awater": self.awater,
            "total_population": self.total_population,
            "coverage": self.coverage,
            "root": self.root,
            "population": self.population,
            "population_density": population_density,
            "display_name": self.display_name,
            "short_geoid": self.short_geoid,
            "square_miles": square_miles,
            "sumlevel": self.sumlevel,
            "simple_name": self.simple_name,
            "sumlevel_name": self.sumlevel_name,
            "parents": parents,
            "census_release": "ACS 2021 5-year",
            "comparatives": comparatives,
            "census_release_level": 5,
        }


GeoParentsResponse = list[Geography]


def build_geo_response(response: dict) -> GeoParentsResponse:
    return [
        Geography(
            full_name=geo_info["display_name"],
            short_name=geo_info["display_name"].split(",")[0].strip(),
            coverage=geo_info["coverage"],
            full_geoid=geo_info["geoid"],
        )
        for geo_info in response["parents"]
    ]


def build_geo_tree(response: GeoParentsResponse) -> Geography | None:
    """
    This takes the response from the cr api and builds it into a tree
    for convience.
    """
    small_to_large = sorted(
        response, 
        key=lambda node: sum_level_priority[node.sumlevel],
        reverse=True
    )
    
    child, *potential_parents = small_to_large
    
    root = child

    level_groups = groupby(
            potential_parents,
            lambda node: node.sumlevel
        )

    for _, group in level_groups:
        child.parents = list(group)
        child = child.primary_parent

    # current geo is the smallest so return
    return root
