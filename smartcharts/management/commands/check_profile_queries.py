from django.core.management.base import BaseCommand
from django.db import connection
from smartcharts.profile import geo_profile, ProfileRequest
from smartcharts.metadata import TimeFrame

class Command(BaseCommand):
    help = "Count the number of queries to build the geo profile template."

    def handle(self, *args, **options):
        request = ProfileRequest("06000US2616322000", TimeFrame.PRESENT)
        _ = geo_profile(request) 
        print(f"The geo_profile function created {len(connection.queries)} queries")

