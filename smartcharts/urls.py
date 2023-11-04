from django.contrib import admin
from django.urls import path
from .views import geography_profile, timeseries_geography_profile

urlpatterns = [
    path("present/", geography_profile),
    path("over-time/", timeseries_geography_profile),
]
