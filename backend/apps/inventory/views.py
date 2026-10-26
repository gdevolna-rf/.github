"""Аренда: публичный каталог, кабинет инвентаря, доступность, акты выдачи/возврата."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.boards.serializers import DeletionResultSerializer
from apps.common.exceptions import NotFound
from apps.inventory import serializers as s
from apps.inventory.models import InventoryItem, InventoryItemPhoto
from apps.inventory.services import handover as handover_service
from apps.inventory.services import items as item_service
from apps.inventory.services import rentals
from apps.organizations.services.access import organization_ids_for

RENTAL_FILTERS = [
    OpenApiParameter("kind", str, description="board | wetsuit | sup | fins | accessory | other (через запятую)"),
    OpenApiParameter("region", str, description="slug или id региона"),
    OpenApiParameter("spot", str, description="slug или id спота"),
    OpenApiParameter("organization", str, description="slug или id организации-владельца"),
    OpenApiParameter("owner", str, description="handle владельца-аккаунта"),
    OpenApiParameter("price_max", OpenApiTypes.DECIMAL, description="Цена за день (или за час, если дневной нет) до"),
    OpenApiParameter("q", str, description="Название, описание, размер, место получения"),
    OpenApiParameter("from", str, description="Начало периода (дата или ISO datetime): только свободные"),
    OpenApiParameter("to", str, description="Конец периода (дата включительно или ISO datetime)"),
]


class OrgContextMixin:
    def get_serializer_context(self):
        context = super().get_serializer_context()
        user = self.request.user
        context["my_org_ids"] = set(organization_ids_for(user)) if user.is_authenticated else set()
        return context


@extend_schema(tags=["rentals"], parameters=RENTAL_FILTERS, summary="Каталог аренды (RENT-01)")
class RentalListView(OrgContextMixin, generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = s.RentalCardSerializer

    def get_queryset(self):
        qs = rentals.filter_rentals(rentals.public_rentals(), self.request.query_params)
        return rentals.card_queryset(qs).order_by("-created_at")


@extend_schema(tags=["rentals"], parameters=[
    OpenApiParameter("from", str, description="Интервалы с этого момента (по умолчанию — текущие и будущие)"),
    OpenApiParameter("to", str, description="Интервалы до этого момента")],
    summary="Экземпляр аренды + занятые интервалы (без данных клиентов)")
class RentalDetailView(OrgContextMixin, generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = s.RentalDetailSerializer

    def get_object(self):
        item = rentals.card_queryset(rentals.public_rentals()).filter(pk=self.kwargs["pk"]).first()
        if item is None:
            raise NotFound("Объявление не найдено.", code="rental_not_found")
        return item

    def retrieve(self, request, *args, **kwargs):
        item = self.get_object()
        start, end = rentals.parse_range(request.query_params)
        context = {**self.get_serializer_context(), "booked_intervals": rentals.booked_intervals(item, start, end)}
        return Response(s.RentalDetailSerializer(item, context=context).data)


# ================================================================= кабинет

def _cabinet_item(item_id):
    return rentals.card_queryset(InventoryItem.objects.filter(pk=item_id)).get()


def _item_response(request, item_id, status_code=status.HTTP_200_OK):
    context = {"request": request, "my_org_ids": set(organization_ids_for(request.user))}
    return Response(s.InventoryItemCabinetSerializer(_cabinet_item(item_id), context=context).data, status=status_code)


@extend_schema_view(
    get=extend_schema(tags=["inventory"], parameters=[
        OpenApiParameter("organization", OpenApiTypes.UUID, description="Инвентарь организации (без — личный)"),
        OpenApiParameter("status", str, description="available | reserved | sold | maintenance | retired"),
        OpenApiParameter("kind", str), OpenApiParameter("purpose", str), OpenApiParameter("q", str)],
        summary="Мой инвентарь (RENT-02)"),
    post=extend_schema(tags=["inventory"], request=s.InventoryItemWriteSerializer,
                       responses={201: s.InventoryItemCabinetSerializer},
                       summary="Добавить экземпляр: личный — направление «Прокат», организации — её сотрудник"),
)
class MyInventoryView(OrgContextMixin, generics.ListCreateAPIView):
    serializer_class = s.InventoryItemCabinetSerializer

    def get_queryset(self):
        params = self.request.query_params
        qs = item_service.list_items(self.request.user, params.get("organization"))
        if params.get("status"):
            qs = qs.filter(status__in=params["status"].split(","))
        if params.get("kind"):
            qs = qs.filter(kind__in=params["kind"].split(","))
        if params.get("purpose"):
            qs = qs.filter(purpose__in=params["purpose"].split(","))
        if params.get("q"):
            qs = qs.filter(title__icontains=params["q"].strip())
        return rentals.card_queryset(qs).order_by("-created_at")

    def create(self, request, *args, **kwargs):
        serializer = s.InventoryItemWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = item_service.create_item(request.user, serializer.validated_data, request=request)
        return _item_response(request, item.pk, status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(tags=["inventory"], responses=s.InventoryItemCabinetSerializer),
    patch=extend_schema(tags=["inventory"], request=s.InventoryItemWriteSerializer,
                        responses=s.InventoryItemCabinetSerializer),
    delete=extend_schema(tags=["inventory"], responses=DeletionResultSerializer,
                         summary="Удалить; при бронях/обращениях — списание (result=retired)"),
)
class MyInventoryItemView(generics.GenericAPIView):
    serializer_class = s.InventoryItemCabinetSerializer

    def get(self, request, pk):
        return _item_response(request, item_service.item_for_manager(request.user, pk).pk)

    def patch(self, request, pk):
        item = item_service.item_for_manager(request.user, pk)
        serializer = s.InventoryItemWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data.pop("organization_id", None)  # владелец не меняется
        data.pop("photo_ids", None)
        item_service.update_item(request.user, item, data, request=request)
        return _item_response(request, item.pk)

    def delete(self, request, pk):
        item = item_service.item_for_manager(request.user, pk)
        return Response({"result": item_service.delete_item(request.user, item, request=request)})


class MyInventoryStatusView(APIView):
    @extend_schema(tags=["inventory"], request=s.InventoryStatusSerializer, responses=s.InventoryItemCabinetSerializer,
                   summary="Статус: available | maintenance | retired | sold")
    def post(self, request, pk):
        item = item_service.item_for_manager(request.user, pk)
        serializer = s.InventoryStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item_service.change_status(request.user, item, serializer.validated_data["status"], request=request)
        return _item_response(request, item.pk)


def _photos_payload(item):
    photos = InventoryItemPhoto.objects.filter(item=item).select_related("media").order_by("position", "id")
    return {"photos": s.ItemPhotoSerializer(photos, many=True).data}


class MyInventoryPhotosView(APIView):
    @extend_schema(tags=["inventory"], request=s.InventoryPhotoAddSerializer, responses={201: s.InventoryPhotosSerializer},
                   summary="Добавить фото (purpose item_photo, ≤10)")
    def post(self, request, pk):
        item = item_service.item_for_manager(request.user, pk)
        serializer = s.InventoryPhotoAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item_service.add_photos(item, request.user, serializer.validated_data["media_ids"])
        return Response(_photos_payload(item), status=status.HTTP_201_CREATED)


class MyInventoryPhotoOrderView(APIView):
    @extend_schema(tags=["inventory"], request=s.InventoryPhotoOrderSerializer, responses=s.InventoryPhotosSerializer,
                   summary="Порядок фото (первое — обложка)")
    def put(self, request, pk):
        item = item_service.item_for_manager(request.user, pk)
        serializer = s.InventoryPhotoOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item_service.reorder_photos(item, serializer.validated_data["ids"])
        return Response(_photos_payload(item))


class MyInventoryPhotoView(APIView):
    @extend_schema(tags=["inventory"], responses=s.InventoryPhotosSerializer, summary="Удалить фото")
    def delete(self, request, pk, photo_id):
        item = item_service.item_for_manager(request.user, pk)
        item_service.delete_photo(item, photo_id)
        return Response(_photos_payload(item))


class MyInventoryAvailabilityView(APIView):
    @extend_schema(tags=["inventory"], responses=s.InventoryAvailabilitySerializer, parameters=[
        OpenApiParameter("from", str, description="Начало периода (по умолчанию — сейчас)"),
        OpenApiParameter("to", str, description="Конец периода (по умолчанию — +24 ч)"),
        OpenApiParameter("organization", OpenApiTypes.UUID, description="Инвентарь организации"),
        OpenApiParameter("kind", str, description="Например, board — для «Свободных бордов»")],
        summary="Занятые интервалы и сводка «Свободных бордов» / «Забронировано» (RENT-03/04)")
    def get(self, request):
        params = request.query_params
        start, end = rentals.parse_range(params)
        data = rentals.availability_overview(request.user, params.get("organization"), start, end, params.get("kind"))
        return Response(s.InventoryAvailabilitySerializer(data).data)


class BookingHandoverView(APIView):
    @extend_schema(tags=["rentals"], request=s.HandoverWriteSerializer, responses={201: s.HandoverSerializer},
                   summary="Акт выдачи (confirmed → in_progress) или возврата (in_progress → completed) — RENT-06")
    def post(self, request, pk):
        serializer = s.HandoverWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        handover = handover_service.record_handover(request.user, pk, serializer.validated_data, request=request)
        return Response(s.HandoverSerializer(handover).data, status=status.HTTP_201_CREATED)


class BookingHandoversView(APIView):
    @extend_schema(tags=["rentals"], responses=s.HandoverSerializer(many=True),
                   summary="Акты по брони — клиенту и исполнителю")
    def get(self, request, pk):
        handovers = handover_service.list_handovers(request.user, pk)
        return Response(s.HandoverSerializer(handovers, many=True).data)
