from django.urls import path

from . import api

app_name = "catalog"

urlpatterns = [
    path("trades/", api.TradeList.as_view(), name="trades"),
    path("trades/<int:trade_id>/specialties/", api.SpecialtyList.as_view(), name="specialties"),
    path("service-areas/", api.ServiceAreaList.as_view(), name="service-areas"),
]
