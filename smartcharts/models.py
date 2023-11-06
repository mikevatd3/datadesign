"""
Data Design

This module holds all of the models that are necessary to describe a design
as it will appear on the profile page. It helps organize all the requested data
into key datapoints separating the design process from the api calls, which can
be collected, dispatched to the various apis, the results of witch can be returned
to the recalling datapoints automatically.
"""

from functools import reduce

from django.db import models
from django.conf import settings
from django.core.cache import cache
from polymorphic.models import PolymorphicModel, PolymorphicManager

from lesp.analyze import extract_variables

from .metadata import (
    ChoiceEnum,
    TimeFrame,
    ComparisonType,
    DataParadigm,
    TableMetadata,
    EditionMetadata,
    VariableMetadata,
    TableMetadataPlaceholder,
    TableMetadataRequest,
    ComparisonEditions,
)
from .saturate import saturate_datapoint
from .utils import make_snake


class ColumnWidth(float, ChoiceEnum):
    """
    This is how you set the column width on the DataDesign that you're building.
    It will help avoid over filling the row, or giving the js incorrect column
    widths.
    """

    QUARTER = 1 / 4
    THIRD = 1 / 3
    HALF = 1 / 2
    TWO_THIRDS = 2 / 3
    THREE_QUARTERS = 3 / 4
    FULL = 1


def hyphenated_name(column_width: ColumnWidth) -> str:
    return "column-" + column_width.name.replace("_", "-").lower()


class DataPoint(models.Model):
    """
    This is the container for a recipe that takes the Census or D3 variables
    and produces an aggregated datapoint.
    """

    identifier = models.CharField(max_length=128) # This name is used to id in the system
    display_name = models.CharField(max_length=256) # This name is what is shown on the page
    lesp_code = models.TextField()

    @property
    def shopping_list(self):
        """
        Returns every token that is not an operator, bracket, or number from
        the program string.
        """
        return {var[:-3] for var in extract_variables(self.lesp_code)}

    def evaluate(self, geography, api_response):
        """
        This will return a filled datapoint.
        """
        return saturate_datapoint(
            self.display_name,
            api_response,
            geography.show_detailed_lineage(),
            self.lesp_code,
        )

    def __str__(self):
        return self.identifier


def fill_metadata_from_response(
    data_point: DataPoint, api_response, metadata_response
):
    # MOVE THIS INTO ANOTHER FILE
    # This will just pull the first table of the list if there
    # is several, define metadata for more complicated lesp_codes.
    table_id = data_point.shopping_list.pop() # This is a little breaky
    table_metadata = metadata_response.tables.get(table_id.lower())
    match table_metadata:
        case TableMetadata():
            return table_metadata
        case TableMetadataPlaceholder():
            return TableMetadata(
                table_name=table_id,
                category="",
                description=api_response["tables"][table_id]["title"],
                description_simple=api_response["tables"][table_id]["title"],
                table_topics="",
                universe=api_response["tables"][table_id]["universe"],
                subject_area="",
                source=api_response["release"]["name"],
                documentation="",
                variables={
                    var_id: VariableMetadata(
                        variable_name=var_id,
                        description=var["name"],
                        indentation=var["indent"],
                        documentation="",
                    )
                    for var_id, var in api_response["tables"][table_id][
                        "columns"
                    ].items()
                },
                all_editions=[],
                comparison_editions=ComparisonEditions(
                    present=EditionMetadata(
                        edition=str(settings.ACS_YEAR_NUMERIC)
                    ),
                    past=EditionMetadata(
                        edition=str(settings.ACS_PAST_YEAR_NUMERIC)
                    ),
                ),
            )
        case _:
            raise TypeError(
                f"table_metadata must be of type TableMetadata or TableMetadataPlaceholder, recieved {type(table_metadata)} for {table_id}."
            )


def populate_year(
    table: TableMetadata, timeframe: TimeFrame
) -> int | str | None:
    try:
        if timeframe == TimeFrame.PRESENT:
            return table.comparison_editions.present.edition
        elif timeframe == TimeFrame.PAST:
            return table.comparison_editions.past.edition

    except AttributeError:
        raise AttributeError(
            f"For the table {table.table_name}, no edition is defined for {timeframe.value}."
        )


class DataDesign(PolymorphicModel):
    """
    Question for later -> how do we make sure these values don't have the leading
    underscore on the admin interface?
    """

    title = models.CharField(max_length=256)
    identifier = models.CharField(max_length=128)
    _width = models.CharField(
        max_length=32, choices=ColumnWidth.to_django_choices()
    )
    # metadata: TableMetadata | None = None
    _comparison_type = models.CharField(
        max_length=16, choices=ComparisonType.to_django_choices()
    )
    _paradigm = models.CharField(
        max_length=2, choices=DataParadigm.to_django_choices()
    )
    compare_geographies = models.BooleanField(default=True)

    child_models = [
        "StatList",
        "ColumnChart",
        "GroupedColumnChart",
    ]

    @property
    def width(self):
        return ColumnWidth[self._width]

    @property
    def comparison_type(self):
        return ComparisonType[self._comparison_type]

    @property
    def paradigm(self):
        return DataParadigm[self._paradigm]

    def collect_shopping_list(self) -> set[TableMetadataRequest]:
        """
        This will return all the variables required to fill this
        design.
        """
        raise NotImplementedError(
            "Cannot call this method on abstract or test class"
        )

    def populate(
        self, geography, api_response, metadata_response, timeframe: TimeFrame
    ):
        """
        Fills all datapoints in the design with calculations and metadata.
        """
        raise NotImplementedError(
            "Cannot call this method on abstract or test class"
        )

    def __str__(self):
        return f"{type(self).__name__}: {self.identifier}"


class StatListManager(PolymorphicManager):
    def get_queryset(self):
        return super().get_queryset().select_related("stat")


class StatList(DataDesign):
    """
    On CR, this is a single value.
    """
    
    STAT_TYPES = [
        ("VAL", "Number"),
        ("PCT", "Percentage"),
        ("DLR", "Dollar"),
        ("COU", "Count"), # Difference between number and count?
    ]

    stat = models.ForeignKey(DataPoint, on_delete=models.SET_NULL, null=True)
    stat_type = models.CharField(max_length=3, choices=STAT_TYPES)
    objects = StatListManager()

    def collect_shopping_list(self) -> set[TableMetadataRequest]:
        return {
            TableMetadataRequest(
                name=table_name,
                comparison_type=self.comparison_type,
                paradigm=self.paradigm,
            )
            for table_name in self.stat.shopping_list
        }

    def populate(
        self,
        geography,
        api_response,
        metadata_response,
        _: TimeFrame = TimeFrame.PRESENT, # Stat lists have no over-time
    ):
        metadata = fill_metadata_from_response(
            self.stat, api_response, metadata_response
        )

        stat = self.stat.evaluate(geography, api_response)
        metadata = {
            "chart_type": "stat_list",
            "stat_type": "count",
            **metadata.to_dict(),
            "column_width": hyphenated_name(self.width),
        }

        stat["metadata"] = metadata
        return {
            "stat": stat,
            "metadata": metadata,
        }


class ColumnChartManager(PolymorphicManager):
    def get_queryset(self):
        return super().get_queryset().select_related("columns")


class ColumnChart(DataDesign):
    """
    A basic vertical bar chart.
    """

    columns = models.ManyToManyField(DataPoint)
    objects = ColumnChartManager()

    def collect_shopping_list(self) -> set[TableMetadataRequest]:
        return {
            TableMetadataRequest(
                name=table_name,
                comparison_type=self.comparison_type,
                paradigm=self.paradigm,
            )
            for column in self.columns.all() 
            for table_name in column.shopping_list
        }
    
    def sub_populate(
        self,
        geography,
        api_response,
        metadata_response,
        timeframe: TimeFrame = TimeFrame.PRESENT,
    ):
        metadata = fill_metadata_from_response(
            self.columns.first(), api_response, metadata_response
        )

        return {
            "name": self.title,
            **{
                make_snake(column.display_name): column.evaluate(
                    geography, api_response
                )
                for column in self.columns.all()
            },
            "metadata": {
                "name": f"{self.title}",
            },
        }

    def populate(
        self,
        geography,
        api_response,
        metadata_response,
        timeframe: TimeFrame = TimeFrame.PRESENT,
    ):
        metadata = fill_metadata_from_response(
            self.columns.first(), api_response, metadata_response
        )

        return {
            "name": self.title,
            **{
                make_snake(column.display_name): column.evaluate(
                    geography, api_response
                )
                for column in self.columns.all()
            },
            "metadata": {
                "name": f"{self.title} ({populate_year(metadata, timeframe)})",
                "chart_type": "chart-column",
                "column_width": hyphenated_name(self.width),
                "table_id": metadata.table_name,
                "universe": metadata.universe,
                "acs_release": populate_year(metadata, timeframe),
                "year": populate_year(metadata, timeframe),
            },
        }


class DoughnutChart(DataDesign):
    """
    A basic pie chart
    """

    slices = models.ManyToManyField(DataPoint)

    def collect_shopping_list(self) -> set[TableMetadataRequest]:
        return {
                    TableMetadataRequest(
                        name=table_name,
                        comparison_type=self.comparison_type,
                        paradigm=self.paradigm,
                    )
                    for slice in self.slices.all() 
                    for table_name in slice.shopping_list
                }

    def populate(
        self,
        geography,
        api_response,
        metadata_response,
        timeframe: TimeFrame = TimeFrame.PRESENT,
    ):
        metadata = fill_metadata_from_response(
            self.slices.first(), api_response, metadata_response
        )

        return {
            "name": f"{self.title} ({populate_year(metadata, timeframe)})",
            "metadata": {
                "name": f"{self.title} ({populate_year(metadata, timeframe)})",
                "chart_type": "chart-pie",
                "column_width": hyphenated_name(self.width),
                "table_id": metadata.table_name,
                "universe": metadata.universe,
                "acs_release": populate_year(metadata, timeframe),
                "year": populate_year(metadata, timeframe),
            },
            **{
                make_snake(slice.display_name): slice.evaluate(geography, api_response)
                for slice in self.slices.all()
            },
        }


class GroupedColumnChart(DataDesign):
    """
    A grouped version of column charts.
    """

    sub_charts = models.ManyToManyField(ColumnChart)
    
    def collect_shopping_list(self) -> set[TableMetadataRequest]:
        return reduce(
            lambda a, b: a | b,
            (chart.collect_shopping_list() for chart in self.sub_charts.all()),
            set(),
        )

    def populate(
        self,
        geography,
        api_response,
        metadata_response,
        timeframe: TimeFrame = TimeFrame.PRESENT,
    ):
        metadata = fill_metadata_from_response(
            self.sub_charts.first().columns.first(), api_response, metadata_response
        )

        return {
            "name": self.title,
            "metadata": {
                "name": self.title,
                "chart_type": "chart-grouped_column",
                "column_width": hyphenated_name(self.width),
                "table_id": metadata.table_name,
                "universe": metadata.universe,
                "acs_release": populate_year(metadata, timeframe),
                "year": populate_year(metadata, timeframe),
                "chart_type": "chart-grouped_column",
            },
            **{
                make_snake(chart.title): chart.sub_populate(
                    geography, api_response, metadata_response
                )
                for chart in self.sub_charts.all()
            },
        }

class Row(models.Model):
    """
    A row of visualizations.
    """

    title = models.CharField(max_length=256, blank=True, null=True)
    documentation = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0, blank=False, null=False)
    # Grouped means that the top rule is removed.
    grouped = models.BooleanField(default=False)
    items = models.ManyToManyField(DataDesign, through="RowItem")
    section = models.ForeignKey(
        "Section", on_delete=models.CASCADE, related_name="rows"
    )

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"Row: {self.title}"

    def collect_shopping_list(self):
        return reduce(
            lambda a, b: a | b,
            (item.collect_shopping_list() for item in self.items.all()),
            set(),
        )

    def populate(
        self,
        geography,
        api_response,
        metadata_response,
        timeframe: TimeFrame = TimeFrame.PRESENT,
    ):
        """
        This will call populate on all the designs, but what should it
        return?
        """
        return {
            "title": self.title,
            "designs": {
                make_snake(design.title): design.populate(
                    geography, api_response, metadata_response, timeframe
                )
                for design in self.items.order_by("rowitem__order")
            },
        }


class RowItem(models.Model):
    row = models.ForeignKey(Row, on_delete=models.CASCADE)
    item = models.ForeignKey(DataDesign, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0, blank=False, null=False)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.item.title


class Factoid(models.Model):
    data_points = models.ManyToManyField(DataPoint)
    template_string = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.template_string


class Section(models.Model):
    title = models.CharField(max_length=1024)
    order = models.PositiveIntegerField(default=0, blank=False, null=False)
    profile = models.ForeignKey(
        "Profile", on_delete=models.CASCADE, related_name="sections"
    )

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.title

    def collect_shopping_list(self):
        return reduce(
            lambda a, b: a | b,
            (row.collect_shopping_list() for row in self.rows.all()),
            set(),
        )

    def fill_factoids(self, *args, **kwargs):
        return dict()

    def populate(
        self,
        geography,
        api_response,
        metadata_response,
        timeframe: TimeFrame = TimeFrame.PRESENT,
    ):
        """
        Same as row. Not sure what to call here, maybe return a dictionary
        matching what is expected by CR?
        """
        return {
            "title": self.title,
            "rows": {
                make_snake(row.title): row.populate(
                    geography, api_response, metadata_response
                )
                for row in self.rows.order_by("order")
            },
            **self.fill_factoids(
                geography, api_response, metadata_response, timeframe
            ),
        }


class Profile(models.Model):
    title = models.CharField(max_length=1024)

    def __str__(self):
        return self.title

    def collect_shopping_list(self):
        return reduce(
            lambda a, b: a | b,
            (
                section.collect_shopping_list()
                for section in self.sections.all()
            ),
            set(),
        )

    def populate(
        self,
        geography,
        api_response,
        metadata_response,
        timeframe: TimeFrame = TimeFrame.PRESENT,
    ):
        return {
            "geography": geography.wrap_up(),
            "sections": {
                make_snake(section.title): section.populate(
                    geography, api_response, metadata_response, timeframe
                )
                for section in self.sections.order_by("order")
            },
            "release": "ACS 2019 5-year",
        }


def get_profile_template():

    if (profile := cache.get("profile")):
        return profile

    profile =  Profile.objects.prefetch_related(
        "sections",
        "sections__rows",
        "sections__rows__items",
    ).first()

    cache.set("profile", profile, 10)

    return profile


# Zoom levels -- when to show parcels.
# Leaflet basemaps

# Sign-up form
# Login page
# Password reset
# Email speed bump
# Password
# Character limit on email address, have it set to 1000?
