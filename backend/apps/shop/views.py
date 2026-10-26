from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.shop.models import Product
from apps.shop.serializers import (
    ShopProductCardSerializer,
    ShopProductDetailSerializer,
    ShopProductInterestInputSerializer,
    ShopProductInterestSerializer,
)
from apps.shop.services import products as service


class ProductListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ShopProductCardSerializer

    def get_queryset(self):
        return service.filter_products(service.public_products(), self.request.query_params)

    @extend_schema(
        parameters=[OpenApiParameter("category", OpenApiTypes.STR, enum=Product.Category.values),
                    OpenApiParameter("status", OpenApiTypes.STR, enum=service.PUBLIC_STATUSES)],
        summary="Витрина мерча (в продаже и предзаказ)", tags=["shop"])
    def get(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response([service.product_card(p) for p in page])


class ProductDetailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses=ShopProductDetailSerializer, summary="Карточка товара (без оплаты, PAY-03)", tags=["shop"])
    def get(self, request, slug):
        return Response(service.product_detail(service.get_public_product(slug), request.user))


class ProductInterestView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=ShopProductInterestInputSerializer,
                   responses={201: ShopProductInterestSerializer, 200: ShopProductInterestSerializer},
                   summary="«Сообщить о поступлении» (идемпотентно)", tags=["shop"])
    def post(self, request, pk):
        data = ShopProductInterestInputSerializer(data=request.data or {})
        data.is_valid(raise_exception=True)
        interest, created = service.add_interest(pk, request.user, data.validated_data.get("variant_id"))
        return Response(service.interest_data(interest),
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @extend_schema(responses={204: None}, summary="Отписаться от уведомления о поступлении", tags=["shop"])
    def delete(self, request, pk):
        service.remove_interest(pk, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
