"""
Build item is coupled to the CR api responses, where lesp is not.
"""

from dataclasses import dataclass, field, asdict
from lesp.core import execute

from .datatypes import TerracedValue, Relation, Estimate, TerracedEstimate
from .namespace import Namespace


def rounded_ratio(first: float | int, second: float | int) -> int:
    return round(round(first / second, 2) * 100)


def index_to_main_geo(values: TerracedValue) -> TerracedValue:
    root_geo_value = values["this"]
    return {
        key: rounded_ratio(root_geo_value, value)
        for key, value in values.items()
    }


def transpose_estimate(
    distributions: dict[Relation, Estimate]
) -> TerracedEstimate:
    result = TerracedEstimate()

    for relation, distribution in distributions.items():
        result.values[relation] = distribution.value
        result.error[relation] = distribution.error
        result.numerators[relation] = distribution.numerator
        result.numerator_errors[relation] = distribution.numerator_moe
        result.error_ratio[relation] = distribution.error_ratio

    result.index = index_to_main_geo(result.values)

    return result


def saturate_datapoint(
    name: str,
    api_response: dict,
    parents: list[dict[str, str]],
    lesp_code: str,
):
    estimates = {
        geography["relation"]: execute(
            lesp_code,
            namespace=Namespace(api_response["data"][geography["geoid"]]),
        )
        for geography in parents
    }

    terraced_estimate = transpose_estimate(estimates)

    return {"name": name, **asdict(terraced_estimate)}
