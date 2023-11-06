import logging
from unittest.mock import Mock

import pytest
from returns.result import Result, Success, Failure

from ..profile import ProfileRequest, TimeFrame
from ..s3handler import S3Handler
from ..build_manager import GeoProfileBuilder


class mock_func:
    def __init__(self, function):
        self._was_called = False
        self.function = function
        self.__name__ = function.__name__

    def __call__(self, *args, **kwargs):
        self._was_called = True
        return self.function(*args, **kwargs)

    def reset(self):
        self._was_called = False

    @property
    def was_called(self):
        return self._was_called


logger = logging.getLogger()


@pytest.fixture
def mock_profile():
    @mock_func
    def profile(_: ProfileRequest):
        return {
            "a": "an",
            "b": "example",
            "c": "profile",
        }

    return profile


@pytest.fixture
def mock_enhance_profile():
    @mock_func
    def enhance_profile(profile):
        return profile

    return enhance_profile


@pytest.fixture
def cache_handler(monkeypatch):
    def mock_check_cache(_, request: ProfileRequest) -> Result:
        if request.geoid == "A":
            return Success({"a": 999, "b": 9999, "c": 99999})
        return Failure("The profile from this geoid is not in the cache.")

    def mock_cache_profile(
        _, request: ProfileRequest, profile: dict[str, str]
    ) -> None:
        pass

    monkeypatch.setattr(S3Handler, "__init__", lambda *_: None)
    monkeypatch.setattr(S3Handler, "check_cache", mock_check_cache)
    monkeypatch.setattr(S3Handler, "cache_profile", mock_cache_profile)

    return S3Handler()  # type: ignore


def test_build_geoid_cache_success(
    cache_handler, mock_profile, mock_enhance_profile
):
    request = ProfileRequest("A", TimeFrame.PAST)
    builder = GeoProfileBuilder(
        cache_handler, mock_profile, mock_enhance_profile, logger
    )

    builder.build_geoid(request)

    assert not mock_profile.was_called


def test_build_geoid_cache_failure(
    cache_handler, mock_profile, mock_enhance_profile
):
    request = ProfileRequest("B", TimeFrame.PRESENT)
    builder = GeoProfileBuilder(
        cache_handler, mock_profile, mock_enhance_profile, logger
    )

    builder.build_geoid(request)

    assert mock_profile.was_called


def test_build_geoid(cache_handler, mock_profile, mock_enhance_profile):
    request = ProfileRequest("A", TimeFrame.PAST)
    builder = GeoProfileBuilder(
        cache_handler, mock_profile, mock_enhance_profile, logger
    )

    profile = builder.build_geoid(request)

    assert profile["a"] == 999 
    assert profile["b"] == 9999
    assert profile["c"] == 99999
    

def test_build_geoid_fresh(cache_handler, mock_profile, mock_enhance_profile):
    request = ProfileRequest("B", TimeFrame.PAST)
    builder = GeoProfileBuilder(
        cache_handler, mock_profile, mock_enhance_profile, logger
    )

    profile = builder.build_geoid(request)

    assert profile["a"] == "an" 
    assert profile["b"] == "example"
    assert profile["c"] == "profile"
