from typing import Callable
import json

from returns.result import Success, Failure
from django.utils.safestring import SafeString

from .utils import LazyEncoder
from .s3handler import CacheHandler
from .profile import ProfileRequest


class GeoProfileBuilder:
    def __init__(
        self,
        cache_handler: CacheHandler,
        builder: Callable[[str], dict],
        enhancer: Callable[[dict], dict],
        logger,
    ):
        self.cache_handler = cache_handler
        self.builder = builder
        self.enhancer = enhancer
        self.logger = logger

    def build_geoid(self, request: ProfileRequest):
        result = self.cache_handler.check_cache(request)

        match result:
            case Success(profile):
                return profile

            case Failure(message):
                self.logger.warning(message)
                profile = self.run_builder(request)
                self.cache_handler.cache_profile(request, profile)

                return profile
            
    def run_builder(self, request: ProfileRequest):
        profile = self.builder(request)
        
        ### THIS LOGIC SHOULD BE REFACTORED OUT TO THE PASSED BUILDER
        # handle this after combining sdc profile.py refactor
        
        # profile["acs_year"] = request.year
        # profile["acs_year_numeric"] = request.year_numeric
        profile = self.enhancer(profile)

        data_dump = json.dumps(profile, cls=LazyEncoder)
        profile["profile_data_json"] = SafeString(data_dump)

        #############################################################

        return profile


    def check_line_items(self, profile_response):
        """
        This will check the response from s3, look at the
        structure and identify what's missing.
        """

    def complete_order(self, profile_response, order):
        """
        This will send a partial list of calculations to create
        at create_profile, and then it will.
        """

