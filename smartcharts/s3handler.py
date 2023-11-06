from abc import ABC

from io import BytesIO
import json
import gzip

from django.utils.safestring import SafeString

import boto3
import botocore

from returns.result import Result, Success, Failure
from .profile import ProfileRequest


class CacheHandler(ABC):
    """
    An abstract class for caching to wherever works for you.

    Need to complete the interface to this.
    """

    def check_cache(self, *args, **kwargs):
        pass

    def write_profile_json(self, *args, **kwargs):
        pass


class S3Handler(CacheHandler):
    def __init__(
        self,
        aws_key: str,
        aws_secret: str,
        servername: str,
        root_file: str,
        profile_version: str,
        dont_check: bool = False,
        dont_update: bool = False,
    ):
        self.servername = servername
        self.root_file = root_file
        self.profile_version = profile_version

        if (not dont_check) | (not dont_update):
            session = boto3.Session(
                aws_access_key_id=aws_key,
                aws_secret_access_key=aws_secret,
                region_name="us-east-2",
            )
            self.s3 = session.resource("s3")

        if dont_check:
            self.check_cache = self.dont_check_cache

        if dont_update:
            self.cache_profile = self.dont_cache_profile

    def to_keyname(self, request: ProfileRequest):
        return f"1.0/data/{self.root_file}/{request.timeframe.value.lower()}/{request.geoid.upper()}"

    def dont_check_cache(self, request: ProfileRequest) -> Result:
        return Failure("This S3 handler is configured to skip checking the cache.")

    def check_cache(self, request: ProfileRequest) -> Result:
        s3_object = self.s3.Object(self.servername, self.to_keyname(request))

        try:
            s3_object.load()

        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return Failure("This geoid hasn't been cached for this year yet.")
            else:
                return Failure("There is an error connecting to S3.")
        
        profile_data = self.unpack_response(s3_object)

        if profile_data.get("profile_version", "") == self.profile_version:
            return Success(profile_data)

        return Failure("The profile must be updated for this geoid.")

    def unpack_response(self, s3_object):
        buffer = BytesIO(s3_object.get()["Body"].read())

        compressed = gzip.GzipFile(fileobj=buffer)

        # Read the decompressed JSON from S3
        string_as_bytes = compressed.read()
        profile_data_json = string_as_bytes.decode()

        # Load it into a Python dict for the template
        profile_data = json.loads(profile_data_json)
        profile_data["profile_data_json"] = SafeString(profile_data_json)

        return profile_data

    def dont_cache_profile(self, request: ProfileRequest, profile: dict):
        pass

    def cache_profile(self, request: ProfileRequest, profile: dict):
        s3_object = self.s3.Object(self.servername, self.to_keyname(request))
        profile.update({"profile_version": self.profile_version})
        profile_json = json.dumps(profile)

        self.write_profile_json(s3_object, profile_json, request)

    def write_profile_json(self, s3_object, profile_json, request: ProfileRequest):
        data_as_bytes = str.encode(profile_json)

        # create gzipped version of json in memory
        memfile = BytesIO()

        with gzip.GzipFile(
            filename=self.to_keyname(request), mode="wb", fileobj=memfile
        ) as gzip_data:
            gzip_data.write(data_as_bytes)
        memfile.seek(0)

        # store static version on S3
        s3_object.put(
            Body=memfile,
            ContentType="application/json",
            ContentEncoding="gzip",
            StorageClass="REDUCED_REDUNDANCY",
        )
