import math
from django.test import TestCase
from ..metadata import (
    TableMetadataRequest,
    TimeFrame,
    ComparisonType,
    DataParadigm,
)

from lesp.core import execute

from ..models import StatList, ColumnWidth, DataPoint, Row, Section, Profile
from ..api_client.geography import Geography
from ..saturate import saturate_datapoint
from ..saturate.namespace import Namespace
from ..saturate.datatypes import Estimate
from ..profile import geo_profile, ProfileRequest
from ..api_client import ApiClient


class TestSmartCharts(TestCase):
    """
    Tests for the smart charts system.
    """

    def setUp(self):
        self.profile = Profile.objects.create(title="Test Profile")
        self.section = Section.objects.create(
            title="Test Section", order=0, profile=self.profile
        )

    def test_choice_enum(self):
        self.assertEqual(
            list(ColumnWidth.to_django_choices()),
            [
                ("QUARTER", "QUARTER"),
                ("THIRD", "THIRD"),
                ("HALF", "HALF"),
                ("TWO_THIRDS", "TWO_THIRDS"),
                ("THREE_QUARTERS", "THREE_QUARTERS"),
                ("FULL", "FULL"),
            ],
        )

    def test_column_width(self):
        design = StatList.objects.create(
            title="Test design model",
            _width="QUARTER",
            _comparison_type="BINARY",
            _paradigm="CR",
        )

        self.assertEqual(design.width.value, 0.25)

    def test_shopping_list(self):
        point = DataPoint.objects.create(
            title="Some random junk.",
            lesp_code="(+ B01001001 (/ B01002002 B01010010) B010101001)",
        )

        self.assertEqual(
            point.shopping_list, {"B01001", "B01002", "B01010", "B010101"}
        )

    def test_shopping_list_statlist(self):
        point = DataPoint.objects.create(
            title="Some random junk.",
            lesp_code="(+ B01001001 (/ B01002001 B01010001) B010101001)",
        )

        design = StatList.objects.create(
            title="Test design model",
            _width="QUARTER",
            _comparison_type="BINARY",
            _paradigm="CR",
            stat=point,
        )

        self.assertEqual(
            design.collect_shopping_list(),
            {
                TableMetadataRequest(
                    "B01001",
                    ComparisonType.BINARY,
                    DataParadigm.CR,
                ),
                TableMetadataRequest(
                    "B01002",
                    ComparisonType.BINARY,
                    DataParadigm.CR,
                ),
                TableMetadataRequest(
                    "B01010",
                    ComparisonType.BINARY,
                    DataParadigm.CR,
                ),
                TableMetadataRequest(
                    "B010101",
                    ComparisonType.BINARY,
                    DataParadigm.CR,
                ),
            },
        )

    def test_profile_view(self):
        point = DataPoint.objects.create(
            title="Some random junk.",
            lesp_code="(+ B01001001 (/ B01001002 B01001003))",
        )

        design = StatList.objects.create(
            title="Test design model",
            _width="QUARTER",
            _comparison_type="BINARY",
            _paradigm="CR",
            stat=point,
        )

        row = Row.objects.create(
            title="A test row",
            section=self.section,
        )
        row.items.add(design)

        _ = geo_profile(
            ProfileRequest("06000US2616322000", TimeFrame.PRESENT),
            profile_template=self.profile,
        )

        self.fail("geo_profile didn't error but write more tests!")

    def test_select_related(self):
        # Making sure this doesn't error out
        _ = geo_profile(
            ProfileRequest("06000US2616322000", TimeFrame.PAST),
            profile_template=self.profile,
        )
        self.fail("over time geo_profile didn't error but write more tests!")


class TestGeography(TestCase):
    def test_show_lineage(self):
        geography = Geography(
            "Detroit City, Wayne County, Michigan",
            "06000US2616322000",
            root=True,
        )

        self.assertEqual(
            geography.show_detailed_lineage(),
            [{"geoid": "06000US2616322000", "relation": "this"}],
        )


class TestBuildItem(TestCase):
    def setUp(self):
        self.api_response = {
            "tables": {
                "B01001": {
                    "title": "Sex by Age",
                    "universe": "Total Population",
                    "denominator_column_id": "B01001001",
                    "columns": {
                        "B01001001 ": {"name": "Total:", "indent": 0},
                        "B01001002": {"name": "Male:", "indent": 1},
                    },
                }
            },
            "geography": {
                "06000US2616322000": {"name": "Detroit city, Wayne County, MI"}
            },
            "data": {
                "06000US2616322000": {
                    "B01001": {
                        "estimate": {
                            "B01001001": 60000.0,
                            "B01001002": 20000.0,
                        },
                        "error": {"B01001001": 200.0, "B01001002": 100.0},
                    }
                }
            },
        }

        self.parents_detailed_lineage = [
            {
                "geoid": "06000US2616322000",
                "relation": "this",
            }
        ]  # from show_detailed_lineage on geography object

    def test_namespace(self):
        namespace = Namespace(
            {
                "B01001": {
                    "estimate": {
                        "B01001001": 1000,
                        "B01001002": 2000,
                    },
                    "error": {
                        "B01001001": 10,
                        "B01001002": 90,
                    },
                },
            }
        )

        self.assertEqual(namespace["B01001001"], Estimate(1000, 10))
        self.assertEqual(namespace["B01001002"], Estimate(2000, 90))

    def test_lesp_with_estimates(self):
        namespace = {
            "B0101": Estimate(100, 10),
            "B0102": Estimate(50, 10),
        }

        lesp_code = "(+ B0101 B0102)"

        result = execute(lesp_code, namespace)

        self.assertEqual(Estimate(150, math.sqrt(10**2 + 10**2)), result)

    def test_lesp_again_with_estimates(self):
        self.fail("Test the lesp code / namespace more carefully!")

    def test_lesp_with_namespace(self):
        namespace = Namespace(
            {
                "B01001": {
                    "estimate": {
                        "B01001001": 2000,
                        "B01001002": 1000,
                    },
                    "error": {
                        "B01001001": 10,
                        "B01001002": 90,
                    },
                },
            }
        )

        lesp_code = "(* 100 (/ B01001002 B01001001))"

        result = execute(lesp_code, namespace)

        self.assertEqual(result.value, 50)
        self.assertAlmostEqual(result.error, 4.4930501889)
        self.assertEqual(result.numerator, 1000)
        self.assertEqual(result.numerator_moe, 90)

    def test_saturate_datapoint(self):
        result = saturate_datapoint(
            "Basic Item",
            self.api_response,
            self.parents_detailed_lineage,
            "(* 100 (/ B01001002 B01001001))",
        )

        self.assertAlmostEqual(result["values"]["this"], 100 / 3)
        self.assertEqual(result["numerators"]["this"], 20000)

    def test_evaluate_data_point(self):
        datapoint = DataPoint.objects.create(
            title="A serious data point",
            lesp_code="(* 100 (/ B01001002 B01001001))",
        )

        geography = Geography(
            "Detroit City, Wayne County, Michigan",
            "06000US2616322000",
            root=True,
        )

        result = datapoint.evaluate(
            geography,
            self.api_response,
        )

        self.assertAlmostEqual(result["values"]["this"], 100 / 3)


class TestApiClient(TestCase):
    """
    This requires the API to be running.
    """

    def setUp(self):
        self.client = ApiClient("https://sdcapi.datadrivendetroit.org")

    def _test_get_parents(self):
        geo_obj = self.client.get_full_geography_object("06000US2616322000")
