import logging
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from returns.result import Success, Failure

from .profile import ProfileRequest, geo_profile, enhance_api_data, ProfileFailureModes
from .performance_profile import measure_performance
from .build_manager import GeoProfileBuilder
from .s3handler import S3Handler
from .metadata import TimeFrame


logging.basicConfig()
logger = logging.getLogger(__name__)


def build_s3_handler():
    """
    You should cache this object for some length of time, because 
    it's surprisingly expensive to build.
    """
    return S3Handler(
        settings.AWS_KEY,
        settings.AWS_SECRET,
        settings.AWS_SERVER_NAME,
        settings.AWS_FILE_ROOT,
        settings.PROFILE_VERSION,
        dont_check=settings.DONT_CHECK_CACHE,
        dont_update=settings.DONT_CACHE,
    )


def bob_the_builder(build_strategy=geo_profile, enhancer=enhance_api_data):
    return GeoProfileBuilder(
        # Add the Cache handler of choice, in this case s3
        cache_handler=build_s3_handler(),
        # Provide the builder with the profile creation functions and the logger.
        builder=build_strategy,
        enhancer=enhancer,  # This is a peculiarity of census reporter that I'd like to factor out
        logger=logger,
    )


@measure_performance
def geography_profile(request):
    # Create request object to for the profile builder
    new_request = ProfileRequest(
        geoid="06000US2616322000",
        timeframe=TimeFrame.PRESENT,
    )

    # Create the profile builder to handle the request
    profile_builder = bob_the_builder()

    # Build the profile!
    profile_result = profile_builder.build_geoid(new_request)

    match profile_result:
        case Failure(fail_reason):
            match fail_reason:
                case _:
                    raise Exception
        case Success(profile):
            # This stuff maybe can be factored out to some obj to pass around.
            profile.update(
                {
                    "ACS_YEAR_NUMERIC": settings.ACS_YEAR_NUMERIC,
                    "API_URL": settings.API_URL,
                }
            )

            return render(request, 'smartcharts/profile.html', profile)


def timeseries_geography_profile(_):
    past_request = ProfileRequest(        
        geoid="06000US2616322000",
        timeframe=TimeFrame.PAST,
    )

    present_request = ProfileRequest(
        geoid="06000US2616322000",
        timeframe=TimeFrame.PRESENT,
    )

    profile_builder = bob_the_builder()

    past_profile = profile_builder.build_geoid(past_request)
    present_profile = profile_builder.build_geoid(present_request)
    
    return JsonResponse({
        "current_year": settings.ACS_YEAR_NUMERIC,
        "past_year": settings.ACS_PAST_YEAR_NUMERIC,
        "profile_data_current_year": present_profile,
        "profile_data_past_year": past_profile,
        "profile_data_json_current_year": present_profile[
            "profile_data_json"
        ],
        "profile_data_json_past_year": past_profile["profile_data_json"],
        "ACS_YEAR_NUMERIC": settings.ACS_YEAR_NUMERIC,
        "API_URL": settings.API_URL,
    })


def homepage(_):
    return HttpResponse(
        """
        <h1>SMARTCHARTS HOMEPAGE</h1>
        """
    )
