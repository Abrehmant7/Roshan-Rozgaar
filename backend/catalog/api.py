"""Public, read-only catalog endpoints used to populate React selectors.

Every trade is served from the same paths, so adding a trade in Admin needs no
code change. Inactive entries, and specialties of inactive trades, are hidden.
"""

from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers
from rest_framework.permissions import AllowAny

from .models import ServiceArea, Specialty, Trade


class TradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trade
        fields = ["id", "slug", "name_en", "name_ur", "icon_key"]


class SpecialtySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = ["id", "trade", "slug", "name_en", "name_ur"]


class ServiceAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceArea
        fields = ["id", "city", "sector_code", "name_en", "name_ur"]


class PublicListView(generics.ListAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    pagination_class = None


class TradeList(PublicListView):
    serializer_class = TradeSerializer
    queryset = Trade.objects.filter(is_active=True).order_by("sort_order", "name_en", "id")


class SpecialtyList(PublicListView):
    serializer_class = SpecialtySerializer

    def get_queryset(self):
        # 404 for unknown or retired trades, so their specialties never leak.
        trade = get_object_or_404(Trade, pk=self.kwargs["trade_id"], is_active=True)
        return trade.specialties.filter(is_active=True).order_by("sort_order", "name_en", "id")


class ServiceAreaList(PublicListView):
    serializer_class = ServiceAreaSerializer
    queryset = ServiceArea.objects.filter(is_active=True).order_by(
        "city", "sort_order", "sector_code", "id"
    )
