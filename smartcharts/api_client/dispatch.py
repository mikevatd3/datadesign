"""
This is a great candidate for it's own library.

- Used here
- Used in a similar form in d3census
- Could be used in a census geocoder re-write
"""

from typing import Any
import json
import asyncio

import aiohttp
from aiohttp import ClientSession
from aiohttp.http import HttpProcessingError
from returns.result import Result, Success, Failure


"""
A request manager that is adapted from real python async io example.
"""

async def fetch_json(url: str, params: dict, session: ClientSession) -> Result[str, str]:
    response = await session.request(
        method="GET",
        url=url,
        params=params,
    )

    try:
        response.raise_for_status()

        json = await response.text()
        return Success(json)

    except(
        aiohttp.ClientError, 
        aiohttp.http.HttpProcessingError,
        aiohttp.ClientResponseError,
        ) as e:

        match e:
            # This needs real error management at this point.
            case aiohttp.ClientError | aiohttp.http.HttpProcessingError:
                message = f"Failed with error {e} for URL: {url}"

            case aiohttp.ClientResponseError:
                message = f"Failed with response code {response.status} for URL: {url}"

            case e:
                message = f"Failed with error {e} for url {url}"

        return Failure(message)


async def parse_json(json_response: str) -> Result[list[list[str]], str]:
    try:
        return Success(json.loads(json_response))

    except:
        return Failure(f"Unable to parse json.")


async def workflow(
    # task (url, params)
    task: tuple[str, dict[str,str]],
    session: ClientSession,
    attempts: int = 0,
) -> list[list[str]]:
    attempts = 0
    while attempts < 3:
        url, params = task
        
        json_response = await fetch_json(url, params, session)
        match json_response:
            case Failure(_): # Can we use these messages more effectively?
                attempts+=1
                continue

            case Success(response_str):
                lists = await parse_json(response_str)

                match lists:
                    case Failure(_):
                        attempts+=1
                        continue

                    case Success(result):
                        return result
    
    raise ValueError(json_response)


async def worker(
        queries: Any,
        outbox: list[list[Any]],
        session: ClientSession
    ):
    while queries:
        task = queries.pop()

        result = await workflow(task, session)
        outbox.append(result)


async def request_manager(calls: list[tuple[str, dict[str,str]]]) -> list[list]:
    outbox = []
    async with ClientSession() as session:
        tasks = [
            worker(calls, outbox, session)
            for _ in range(5)
        ]
        await asyncio.gather(*tasks)

    return outbox
