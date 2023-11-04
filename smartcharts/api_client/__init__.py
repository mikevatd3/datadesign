import logging
import time

# refactor to only asyncio
import asyncio
import requests
from returns.result import Success, Failure, Result
from django.conf import settings

from ..metadata import (
    DataParadigm,
    MetadataPool,
    TableMetadataPlaceholder,
    TableMetadataRequest,
    build_metadata_from_response,
)
from .geography import Geography, build_geo_response, build_geo_tree
from .dispatch import request_manager
from .reducer import collapse_several_responses


class HipApiError(Exception):
    """
    Using this to be clear about what calls on the api are failing.
    """


def chunks(lst, n):
    # https://stackoverflow.com/questions/312443/how-do-i-split-a-list-into-equally-sized-chunks
    # This is to not overwhelm the api server with a single huge request
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def build_year(data_paradigm: DataParadigm, year: int):
    if data_paradigm == DataParadigm.CR:
        return f"acs{year}_5yr"
    return f"d3_{year}"


def strip_bad_tables_from_api_error(error: str):
    return error.split()[-1].strip(".").split(",")


def repair_table_call(table_ids, error_tables):
    table_list = table_ids.split(",")
    return ",".join(
        [table for table in table_list if table not in error_tables]
    )


class ApiClient(object):
    def __init__(self, base_url):
        self.base_url = base_url
        self.logger = logging.getLogger()

    def _get(self, path, params=None, max_repairs=3) -> Result:
        for _ in range(max_repairs):
            r = requests.get(self.base_url + path, params=params)
            data = None
            if r.status_code == 200:
                # If the data is good, return data
                data = r.json(object_pairs_hook=dict)
                return Success(data)
            time.sleep(0.05)
        try:
            return Failure(r.json().get("error"))
        except requests.exceptions.JSONDecodeError:
            return Failure(r.content)

    def get_parent_geoids(self, geoid):
        match self._get(
            f"/1.0/geo/tiger{settings.ACS_YEAR_NUMERIC}/{geoid}/parents"
        ):
            case Success(payload):
                return payload
            case Failure(message):
                raise HipApiError("Failed to pull parents from api: " + str(message))

    def get_geoid_data(self, geoid):
        match self._get(f"/1.0/geo/tiger{settings.ACS_YEAR_NUMERIC}/{geoid}"):
            case Success(payload):
                return payload

            case Failure(message):
                raise HipApiError("Failed to get data for geoid: " + str(message))

    def get_data(
        self,
        table_ids: list[str],
        geo_ids: list[str],
        acs="latest",
        num_fixes=20,
    ):
        if (type(table_ids) != list) | (type(geo_ids) != list):
            raise TypeError(
                "You must provide a lists to get_data for table_ids and geo_ids."
            )

        problem_tables = []
        for i in range(num_fixes):
            if not table_ids:
                break

            match self._get(
                f"/1.0/data/show/{acs}",
                params=dict(
                    table_ids=",".join(table_ids), geo_ids=",".join(geo_ids)
                ),
            ):
                case Success(payload):
                    return payload

                case Failure(message):
                    if str(message).startswith(
                        "(psycopg2.errors.UndefinedTable)"
                    ):
                        _, error_table, _ = message.split('"')

                        to_remove = error_table.split("_")[0]
                        problem_tables.append(to_remove.upper())

                        self.logger.warning(
                            f"Unable to pull {','.join(problem_tables)} from schema {acs}--trying the call without them."
                        )

                        table_ids = [
                            table_id
                            for table_id in table_ids
                            if table_id not in problem_tables
                        ]

                    elif str(message).startswith(
                        "The Data Driven Detroit release"
                    ):
                        to_remove = message.strip(".").split()[-1].split(",")
                        problem_tables.extend(
                            [table.upper() for table in to_remove]
                        )
                        self.logger.warning(
                            f"Unable to pull {','.join(problem_tables)} from schema {acs}--trying the call without them."
                        )
                        table_ids = [
                            table_id
                            for table_id in table_ids
                            if table_id not in to_remove
                        ]

                    else:
                        raise HipApiError(str(message))
        raise HipApiError(
            f"Tried to remove {to_remove}, failed on attempt {i}: {str(message)}"
        )

    def get_full_geography_object(self, geoid) -> Geography:
        """
        This is very awkward and needs a refactor.
        """

        # Request all the data needed for this function
        result = asyncio.run(request_manager([
            (self.base_url + f"/1.0/geo/tiger{settings.ACS_YEAR_NUMERIC}/{geoid}", dict()),
            (self.base_url + f"/1.0/geo/tiger{settings.ACS_YEAR_NUMERIC}/{geoid}/parents", dict()),
        ]))
        
        # The easiest way to tell the difference between the two is 
        # pattern match.
        for item in result:
            match item:
                case {"parents": _}:
                    geo_response = build_geo_response(item)
                    parents_tree = build_geo_tree(geo_response)
                case {
                        "type": _,
                        "properties": _,
                        "geometry": None
                    }:
                    properties = item["properties"]
                    geography = Geography(
                        full_geoid=geoid,
                        full_name=properties["display_name"],
                        short_name=properties["simple_name"],
                        land_area=properties["aland"],
                        awater=properties["awater"],
                        total_population=properties["population"],
                        root=True,
                    )
                case _:
                    raise TypeError("Something went wrong in the return from the geography call.")

        geography.parents = parents_tree

        return geography

    def fill_metadata_pool(
        self,
        table_ids: set[TableMetadataRequest],
    ) -> MetadataPool:
        """
        This will be called at the start of the process, and will feed the 
        calls to the api to get the available datasets before calling for the data.
        """

        base_url = self.base_url + "/metadata/tables/"

        tables = {}
        to_dispatch = []
        for table_meta in table_ids:
            if table_meta.paradigm == DataParadigm.D3:
                to_dispatch.append((f"{base_url}{table_meta.name.lower()}", {}))

            else:
                tables[table_meta.name.lower()] = TableMetadataPlaceholder(
                    table_meta.name.lower()
                )

        responses = asyncio.run(request_manager(to_dispatch))

        for response in responses:
            for table_name, raw_obj in response["tables"].items():
                metadata_obj = build_metadata_from_response(raw_obj)
                if metadata_obj is not None:
                    tables[table_name.lower()] = metadata_obj

        return MetadataPool(tables=tables)

    def get_data_dispatched(self, data_request, geographies, chunk_size=8):
        to_dispatch = []
        for (paradigm, year), table_list in data_request.items():
            table_splits = chunks(table_list, chunk_size)
            for split in table_splits:
                params = {
                    "geo_ids": ",".join(geographies),
                    "table_ids": ",".join(
                        [table.table_name.upper() for table in split]
                    ),
                }

                to_dispatch.append(
                    (
                        self.base_url
                        + f"/1.0/data/show/{build_year(paradigm, year)}",
                        params,
                    )
                )
        responses: list[dict] = asyncio.run(
            request_manager(to_dispatch)
        )

        return collapse_several_responses(responses, geographies)
