from enum import Enum, auto
from dataclasses import dataclass
from collections import defaultdict
from pydantic import BaseModel

# This import is an unwanted coupling
from django.conf import settings


"""
Using pydantic here to capture the datadesigns
from the pipeline.
"""


class ChoiceEnum(Enum):
    """
    We're using a pattern here where we use the char field / choices mechanism 
    from django but using getters to wrap those values in Enums before sending 
    to the rest of the program.

    This is coupled sort of to django, but not horribly so.
    """

    @classmethod
    def to_django_choices(cls):
        return zip(cls.__members__.keys(), cls.__members__.keys())


class TimeFrame(ChoiceEnum):
    # Client & Server
    PAST = "past"
    PRESENT = "present"


class ComparisonType(ChoiceEnum):
    # Client
    SINGLE = auto()
    BINARY = auto()
    CONTINUOUS = auto()


class DataParadigm(ChoiceEnum):
    # Client & Server
    CR = auto()
    D3 = auto()


@dataclass(frozen=True, eq=True, slots=True)
class TableMetadataRequest:
    # Client-side
    name: str
    comparison_type: ComparisonType
    paradigm: DataParadigm


@dataclass
class TableDataRequest:
    # Client-side
    name: str
    vars: list[str]
    year: int


class VariableMetadata(BaseModel):
    variable_name: str
    indentation: int
    description: str
    documentation: str | None

    def to_dict(self):
        return {
            "variable_name": self.variable_name,
            "indentation": self.indentation,
            "description": self.description,
            "documentation": self.documentation,
        }


@dataclass
class TableMetadataPlaceholder:
    table_name: str

    def to_dict(self):
        return { "name": self.table_name }


class EditionMetadata(BaseModel):
    edition: str


class ComparisonEditions(BaseModel):
    present: EditionMetadata | None
    past: EditionMetadata | None


class TableMetadata(BaseModel):
    table_name: str
    category: str | None
    description: str | None
    description_simple: str | None
    table_topics: str | None
    universe: str | None
    subject_area: str | None
    source: str | None
    documentation: str | None
    variables: dict[str, VariableMetadata]
    all_editions: list[EditionMetadata]
    comparison_editions: ComparisonEditions
    
    def report_year_for_timeframe(self, timeframe: TimeFrame):
        if timeframe == TimeFrame.PAST:
            return self.comparison_editions.past.edition
        return self.comparison_editions.present.edition

    def to_dict(
            self, 
            timeframe: TimeFrame = TimeFrame.PRESENT
        ):
        return {
            "table_name": self.table_name,
            "category": self.category,
            "description": self.description,
            "description_simple": self.description_simple,
            "table_topics": self.table_topics,
            "universe": self.universe,
            "subject_area": self.subject_area,
            "source": self.source,
            "documentation": self.documentation,
            "variables": {
                var_name: var.to_dict() 
                for var_name, var in self.variables.items()
            },
            "year": self.report_year_for_timeframe(timeframe)
        }


def build_metadata_from_response(table_dict: dict) -> TableMetadata | None:
    return TableMetadata.model_validate(table_dict)


@dataclass
class MetadataPool:
    # Reference Mode (regular)
    """
    This class is not useful off of the client-side and should
    probably be removed from this file to isolate the future parts of
    the d3metadata system.
    """
    tables: dict[str, TableMetadata]

    def prepare_data_request(self, timeframe: TimeFrame) -> dict[str, tuple[list[str], list[str]]]:
        """
        key is the schema-name, list one is the tables to request, list two the
        geoids to request (repeats on all).
        """
        result = defaultdict(list)

        # set years
        if timeframe == TimeFrame.PAST:
            d3_timeframe = 'past'
            census_timeframe = settings.ACS_PAST_YEAR_NUMERIC
        else:
            d3_timeframe = 'present'
            census_timeframe = settings.ACS_YEAR_NUMERIC

        for table in self.tables.values():
            match table:
                case TableMetadata():
                    if getattr(table.comparison_editions, d3_timeframe) is None:
                        continue

                    result[(DataParadigm.D3, d3_timeframe)].append(table)

                case TableMetadataPlaceholder():
                    result[(DataParadigm.CR, census_timeframe)].append(table)
                case _:
                    raise TypeError("You must provide a TableMetadataRequest instance TableMetadataPlaceholder")

        return dict(result)

