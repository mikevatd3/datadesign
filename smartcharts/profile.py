import time
from dataclasses import dataclass
from django.conf import settings

from .models import get_profile_template
from .metadata import TimeFrame
from .api_client import ApiClient
from .utils import get_ratio, SUMMARY_LEVEL_DICT


@dataclass
class ProfileRequest: 
    geoid: str
    timeframe: TimeFrame
    type: str = "single"


def geo_profile(request: ProfileRequest):
    """
    [TEMPLATE] -| get_shopping_list |-> 
    [PROFILE TREE] -| fill_metadata_pool |->
    CHECK DESIGN AGAINST METADATA -> [PREPARED REQUEST] ->
    PROVIDE TIMEFRAME TO REQUEST -> SEND REQUEST TO DISPATCHER -> [API RESULT]
    """
    print("geoprofile started")
    start = time.monotonic()

    api_client = ApiClient(settings.API_URL)
    profile_template = get_profile_template()
    
    print(f"template loaded at {round(time.monotonic() - start, 4)}s")
    
    # Check the design and metadata to prepare accurate data request
    shopping_list = profile_template.collect_shopping_list()
    metadata_pool = api_client.fill_metadata_pool(shopping_list)
    year_data_request = metadata_pool.prepare_data_request(request.timeframe)
    
    print(f"data request prepared at {round(time.monotonic() - start, 4)}s")

    # Pull the data as designed
    geography = api_client.get_full_geography_object(request.geoid)
    namespace = api_client.get_data_dispatched(
       year_data_request, 
       geography.show_lineage(), 
    )

    print(f"api call returned at {round(time.monotonic() - start, 4)}s")
    
    # Fill the tree with the returned data
    profile = get_profile_template().populate(
        geography,
        namespace,
        metadata_pool,
    )
    
    print(f"profile filled at {round(time.monotonic() - start, 4)}s")

    return profile


"""
Past this point is OG Census Reporter and could use a thoughtful refactor.
"""


def find_dicts_with_key(dictionary, searchkey):
    stack = [dictionary]
    dict_list = []
    while stack:
        d = stack.pop()
        if searchkey in d:
            dict_list.append(d)
        for value in d.values():
            if isinstance(value, dict):
                stack.append(value)

    return dict_list


def enhance_api_data(api_data):
    dict_list = find_dicts_with_key(api_data, 'values')

    for d in dict_list:
        raw = {}
        enhanced = {}
        try:
            geo_value = d['values']['this']
        except Exception:
            geo_value = None

        num_comparatives = 2

        # create our containers for transformation
        for obj in ['values', 'error', 'numerators', 'numerator_errors']:
            raw[obj] = d[obj]
            enhanced[obj] = {}
        enhanced['index'] = {}
        enhanced['error_ratio'] = {}
        comparative_sumlevs = []

        # enhance
        for sumlevel in ['this', 'place', 'CBSA', 'county', 'state', 'nation']:

            # favor CBSA over county, but we don't want both
            if sumlevel == 'county' and 'CBSA' in enhanced['values']:
                continue

            # add the index value for comparatives
            if sumlevel in raw['values']:
                enhanced['values'][sumlevel] = raw['values'][sumlevel]
                if geo_value:
                    enhanced['index'][sumlevel] = get_ratio(geo_value, raw['values'][sumlevel])
                else:
                    enhanced['index'][sumlevel] = 0


                # add to our list of comparatives for the template to use
                if sumlevel != 'this':
                    comparative_sumlevs.append(sumlevel)

            # add the moe ratios
            if (sumlevel in raw['values']) and (sumlevel in raw['error']):
                enhanced['error'][sumlevel] = raw['error'][sumlevel]
                enhanced['error_ratio'][sumlevel] = get_ratio(raw['error'][sumlevel], raw['values'][sumlevel], 3)

            # add the numerators and numerator_errors
            if sumlevel in raw['numerators']:
                enhanced['numerators'][sumlevel] = raw['numerators'][sumlevel]

            if (sumlevel in raw['numerators']) and (sumlevel in raw['numerator_errors']):
                enhanced['numerator_errors'][sumlevel] = raw['numerator_errors'][sumlevel]

            if len(enhanced['values']) >= (num_comparatives + 1):
                break

        # replace data with enhanced version
        for obj in ['values', 'index', 'error', 'error_ratio', 'numerators', 'numerator_errors']:
            d[obj] = enhanced[obj]

        api_data['geography']['comparatives'] = comparative_sumlevs

    # Put this down here to make sure geoid is valid before using it
    sumlevel = api_data['geography']['this']['sumlevel']
    api_data['geography']['this']['sumlevel_name'] = SUMMARY_LEVEL_DICT[sumlevel]['name']
    api_data['geography']['this']['short_geoid'] = api_data['geography']['this']['full_geoid'].split('US')[1]
    try:
        release_bits = api_data['geography']['census_release'].split(' ')
        api_data['geography']['census_release_year'] = release_bits[1][2:]
        api_data['geography']['census_release_level'] = release_level = release_bits[2][:1]
    except:
        pass

    # ProPublica Opportunity Gap app doesn't include smallest schools.
    # Originally, this also enabled links to Census narrative profiles,
    # but those disappeared.
    if release_level in ['1','3'] and sumlevel in ['950', '960', '970']:
        api_data['geography']['this']['show_extra_links'] = True

    return api_data
