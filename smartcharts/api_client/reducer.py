"""
Using the weird magic of mergedeep is okay for now,
but it may be better to be more explicit.
"""

from mergedeep import merge


def collapse_several_responses(responses: list[dict], geoids) -> dict:
    result = {}
    for response in responses:
        result = merge(result, response)

    return result

