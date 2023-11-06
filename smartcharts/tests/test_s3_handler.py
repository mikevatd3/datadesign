from dataclasses import dataclass
from io import BytesIO
import json
import logging

import pytest
from hypothesis import given, strategies as st
from returns.result import Failure, Success
import boto3
import botocore
import gzip

from ..profile import ProfileRequest
from ..metadata import TimeFrame
from ..s3handler import S3Handler


logger = logging.getLogger()


@dataclass
class MockGzipFile:
    fileobj: BytesIO
    filename: str = "default"
    mode: str = "r"

    def read(self):
        return self.fileobj.read()

    def write(self, data):
        self.fileobj.write(data)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        pass


class MockResource:
    def __init__(self, initial_cache=dict(), no_internet=False):
        self.cache = initial_cache

        self.cache[
            ("default_servername", "test_key")
        ] = b'{ "key": "value", "profile_version": "0.1.0" }'
        self.cache[
            (
                "default_servername",
                "1.0/data/default_root_file/past/123US500900",
            )
        ] = b'{ "geoid": "123US500900", "profile_version": "0.1.0" }'

    def Object(self, servername, keyname):
        try:
            return self._Object(
                _return_value=self.cache[(servername, keyname)],
                servername=servername,
                key=keyname,
                parent_cache=self.cache,
            )
        except KeyError:
            return self._FailedObject(
                servername=servername, key=keyname, parent_cache=self.cache
            )

    class _Object:
        def __init__(self, _return_value: bytes, servername, key, parent_cache):
            self._return_value = _return_value
            self.servername, self.key = servername, key
            self.parent_cache = parent_cache

            class Body:
                def __init__(self, _return_value):
                    self._return_value = _return_value

                def read(self):
                    return self._return_value

            self.Body = Body

        def get(self):
            return {"Body": self.Body(self._return_value)}

        def load(self):
            pass

        def put(self, Body: BytesIO, *_, **__):
            self.parent_cache[(self.servername, self.key)] = Body.read()

    class _FailedObject:
        def __init__(self, servername, key, parent_cache):
            self.servername, self.key = servername, key
            self.parent_cache = parent_cache

        def load(self):
            raise botocore.exceptions.ClientError(
                error_response={"Error": {"Code": "404"}},
                operation_name="",
            )

        def put(self, Body: BytesIO, *_, **__):
            self.parent_cache[(self.servername, self.key)] = Body.read()

    def resource_check(self):
        return "SUCCESSFUL"


@dataclass
class MockSession:
    aws_access_key_id: str
    aws_secret_access_key: str
    region_name: str

    def resource(self, _):
        return MockResource()


@pytest.fixture
def preloaded_handler(monkeypatch):
    monkeypatch.setattr(boto3, "Session", MockSession)
    monkeypatch.setattr(gzip, "GzipFile", MockGzipFile)

    return S3Handler(
        aws_key="default_aws_key",
        aws_secret="default_aws_secret",
        servername="default_servername",
        root_file="default_root_file",
        profile_version="0.1.0",
    )


# Using hypothesis mostly for fuzzing
@given(
    aws_key=st.characters(),
    aws_secret=st.characters(),
    servername=st.characters(),
    root_file=st.characters(),
    profile_version=st.characters(),
)
def test_init(aws_key, aws_secret, servername, root_file, profile_version):
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(boto3, "Session", MockSession)

        handler = S3Handler(
            aws_key=aws_key,
            aws_secret=aws_secret,
            servername=servername,
            root_file=root_file,
            profile_version=profile_version,
        )

        assert handler.s3.resource_check() == "SUCCESSFUL"


@pytest.mark.parametrize(
    "dont_check,dont_update",
    [
        (False, True),
        (True, False),
        (False, False),
    ],
)
def test_init_all_build_session(dont_check, dont_update):
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(boto3, "Session", MockSession)

        handler = S3Handler(
            aws_key="plotkenbdde",
            aws_secret="ghjkdfjents",
            servername="sdfjsdf",
            root_file="fake_site",
            profile_version="0.1.0",
            dont_check=dont_check,
            dont_update=dont_update,
        )

        assert handler.s3.resource_check() == "SUCCESSFUL"


def test_init_doesnt_build_session():
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(boto3, "Session", MockSession)

        handler = S3Handler(
            aws_key="plotkenbdde",
            aws_secret="ghjkdfjents",
            servername="sdfjsdf",
            root_file="fake_site",
            profile_version="0.1.0",
            dont_check=True,
            dont_update=True,
        )

        with pytest.raises(AttributeError):
            handler.s3.resource_check()


@pytest.mark.parametrize(
    "input,output",
    [
        (
            ProfileRequest("123US500500", TimeFrame.PRESENT),
            "1.0/data/default_root_file/present/123US500500",
        ),
        (
            ProfileRequest("123us500900", TimeFrame.PAST),
            "1.0/data/default_root_file/past/123US500900",
        ),
    ],
)
def test_to_keyname(input, output, preloaded_handler):
    result = preloaded_handler.to_keyname(input)

    assert result == output


def test_unpack_response(preloaded_handler):
    s3_object = MockResource().Object(
        servername="default_servername", keyname="test_key"
    )
    result = preloaded_handler.unpack_response(s3_object)

    assert result == {
        "key": "value",
        "profile_version": "0.1.0",
        "profile_data_json": '{ "key": "value", "profile_version": "0.1.0" }',
    }


def test_check_cache_success(preloaded_handler):
    request = ProfileRequest(geoid="123us500900", timeframe=TimeFrame.PAST)

    logging.warning(preloaded_handler.to_keyname(request))

    result = preloaded_handler.check_cache(request)

    assert result == Success(
        {
            "geoid": "123US500900",
            "profile_version": "0.1.0",
            "profile_data_json": '{ "geoid": "123US500900", "profile_version": "0.1.0" }',
        }
    )


def test_check_cache_failure(preloaded_handler):
    request = ProfileRequest(geoid="broken_key", timeframe=TimeFrame.PAST)
    result = preloaded_handler.check_cache(request)

    assert result == Failure("This geoid hasn't been cached for this year yet.")


def test_write_profile_json(preloaded_handler):
    request = ProfileRequest("TESTGEOID", TimeFrame.PRESENT)
    resource = MockResource()
    s3_object = resource.Object(
        servername="default_servername",
        keyname=preloaded_handler.to_keyname(request),
    )
    profile_json = json.dumps({"this profile value": "some value"})

    preloaded_handler.write_profile_json(s3_object, profile_json, request)

    assert (
        resource.cache[
            ("default_servername", preloaded_handler.to_keyname(request))
        ]
        == b'{"this profile value": "some value"}'
    )


def test_cache_profile(preloaded_handler):
    request = ProfileRequest("12300US4567", TimeFrame.PRESENT)
    profile = {"a": 100, "b": 200, "c": 300}

    # Not sure what to assert here, making sure it runs successfully is
    # okay for now.
    preloaded_handler.cache_profile(request, profile)


def test_cache_and_recover_simple(preloaded_handler):
    request = ProfileRequest("04000US2616322000", TimeFrame.PRESENT)
    profile = {"a": 999, "b": 9999, "c": 9999999}

    # cache
    preloaded_handler.cache_profile(request, profile)

    # recover
    profile = preloaded_handler.check_cache(request)

    assert type(profile) == Success
    assert profile.unwrap()["a"] == 999
    assert profile.unwrap()["b"] == 9999
    assert profile.unwrap()["c"] == 9999999


@given(
    geoid=st.text(),
    a=st.integers(),
    b=st.integers(),
    c=st.characters(),
    timeframe=st.sampled_from(TimeFrame),
)
def test_cache_and_recover_fuzz(geoid, a, b, c, timeframe):
    with pytest.MonkeyPatch().context() as monkeypatch:
        monkeypatch.setattr(boto3, "Session", MockSession)
        monkeypatch.setattr(gzip, "GzipFile", MockGzipFile)

        handler = S3Handler(
            aws_key="default_aws_key",
            aws_secret="default_aws_secret",
            servername="default_servername",
            root_file="default_root_file",
            profile_version="0.1.0",
        )
        request = ProfileRequest(geoid, timeframe)
        profile = {"a": a, "b": b, "c": c}

        # cache
        handler.cache_profile(request, profile)

        # recover
        profile = handler.check_cache(request)

        assert type(profile) == Success
        assert profile.unwrap()["a"] == a
        assert profile.unwrap()["b"] == b
        assert profile.unwrap()["c"] == c
