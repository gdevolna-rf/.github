"""Тонкие представления: права → сервис → сериализатор. Публичный каталог — AllowAny (BR-01, NAV-02)."""
from django.db.models import Exists, OuterRef, Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.boards import serializers as s
from apps.boards.models import BoardMedia, BoardModel, BoardVariant
from apps.boards.services import board_models as model_service
from apps.boards.services import catalog, media as media_service, types as type_service
from apps.boards.services import variants as variant_service
from apps.boards.services import workshops as workshop_service
from apps.boards.services.access import (member_workshop, member_workshop_ids, model_for_member,
                                         my_workshop_membership, variant_for_member)
from apps.boards.services.history import variants_with_history
from apps.common.exceptions import DomainError, NotFound
from apps.organizations.models import Organization

BOARD_FILTERS = [
    OpenApiParameter("type", str, description="Код типа доски (можно несколько через запятую): fish, gun…"),
    OpenApiParameter("region", str, description="slug или id региона мастерской"),
    OpenApiParameter("shaper", str, description="slug мастерской"),
    OpenApiParameter("length_min", str, description="Длина от: дюймы (70) или 5'10\""),
    OpenApiParameter("length_max", str, description="Длина до: дюймы или 6'2\""),
    OpenApiParameter("volume_min", OpenApiTypes.DECIMAL, description="Объём от, л"),
    OpenApiParameter("volume_max", OpenApiTypes.DECIMAL, description="Объём до, л"),
    OpenApiParameter("price_max", OpenApiTypes.DECIMAL, description="Цена варианта до"),
    OpenApiParameter("availability", str, description="in_stock | made_to_order | out_of_stock (через запятую)"),
    OpenApiParameter("material", str, description="id или название материала"),
    OpenApiParameter("repair", OpenApiTypes.BOOL, description="Мастерская делает ремонт (SHP-04)"),
    OpenApiParameter("q", str, description="Модель, мастерская, тип, регион, артикул"),
    OpenApiParameter("ordering", str, enum=list(catalog.MODEL_ORDERING), description="По умолчанию new"),
]
SHAPER_FILTERS = [
    OpenApiParameter("region", str, description="slug или id региона"),
    OpenApiParameter("repair", OpenApiTypes.BOOL, description="Делает ремонт"),
    OpenApiParameter("type", str, description="Есть опубликованная модель этого типа"),
    OpenApiParameter("q", str, description="Мастерская, мастер, регион, город, специализация, модели"),
    OpenApiParameter("ordering", str, enum=list(catalog.SHAPER_ORDERING), description="По умолчанию rating"),
]


class MyWorkshopsContextMixin:
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["my_workshop_ids"] = member_workshop_ids(self.request.user)
        return context


# ================================================================= публичный каталог

@extend_schema(tags=["boards"], parameters=BOARD_FILTERS, summary="«Все доски»: каталог опубликованных моделей")
class BoardListView(MyWorkshopsContextMixin, generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = s.BoardCardSerializer

    def get_queryset(self):
        params = self.request.query_params
        qs = catalog.filter_models(catalog.public_models(), params)
        return catalog.order_models(catalog.card_queryset(qs), params)


@extend_schema(tags=["boards"], summary="Модель доски: варианты, фото, видео, мастерская, is_own")
class BoardDetailView(MyWorkshopsContextMixin, generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = s.BoardDetailSerializer

    def get_queryset(self):
        return catalog.card_queryset(catalog.public_models())

    def get_object(self):
        obj = self.get_queryset().filter(pk=self.kwargs["pk"]).first()
        if obj is None:
            raise NotFound("Модель не найдена или снята с публикации.", code="board_not_found")
        return obj


@extend_schema(tags=["boards"], parameters=SHAPER_FILTERS, summary="«По шейперам»: мастерские с моделями (SHP-08/09)")
class ShaperListView(MyWorkshopsContextMixin, generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = s.ShaperCardSerializer

    def get_queryset(self):
        params = self.request.query_params
        qs = catalog.shaper_queryset(catalog.filter_shapers(catalog.public_workshops(), params))
        return catalog.order_shapers(qs, params)

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        context = self.get_serializer_context()
        context["models_by_workshop"] = catalog.models_by_workshop([o.pk for o in page])
        data = self.get_serializer_class()(page, many=True, context=context).data
        return self.get_paginated_response(data)


@extend_schema(tags=["boards"], summary="Публичный профиль мастерской (SHP-03/04/08/10)")
class ShaperDetailView(MyWorkshopsContextMixin, generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = s.ShaperDetailSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return catalog.shaper_queryset(catalog.public_workshops()).prefetch_related(
            "gallery", "custom_board_types", "custom_materials")

    def get_object(self):
        obj = self.get_queryset().filter(slug=self.kwargs["slug"]).first()
        if obj is None:
            raise NotFound("Мастерская не найдена.", code="shaper_not_found")
        return obj

    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        context = self.get_serializer_context()
        context["models_by_workshop"] = catalog.models_by_workshop([obj.pk], limit=200)
        return Response(self.get_serializer_class()(obj, context=context).data)


@extend_schema(tags=["boards"], parameters=BOARD_FILTERS, summary="Опубликованные модели мастерской")
class ShaperBoardsView(BoardListView):
    def get_queryset(self):
        workshop = catalog.public_workshops().filter(slug=self.kwargs["slug"]).first()
        if workshop is None:
            raise NotFound("Мастерская не найдена.", code="shaper_not_found")
        params = self.request.query_params
        qs = catalog.filter_models(catalog.public_models().filter(workshop=workshop), params)
        return catalog.order_models(catalog.card_queryset(qs), params)


@extend_schema(tags=["boards"], summary="Типы досок для фильтра каталога (стандартные + используемые мастерскими)")
class PublicBoardTypesView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = s.BoardTypeSerializer
    pagination_class = None

    def get_queryset(self):
        return catalog.public_board_types()


@extend_schema(tags=["boards"], summary="Материалы для фильтра каталога")
class PublicMaterialsView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = s.MaterialSerializer
    pagination_class = None

    def get_queryset(self):
        return catalog.public_materials()


# ================================================================= кабинет: мастерская

def _reload_workshop(workshop_id):
    return Organization.objects.select_related("workshop", "workshop__promo_video", "region", "logo", "cover").get(
        pk=workshop_id)


class MyWorkshopView(APIView):
    """GET — первая мастерская, где я активный участник (или 404 no_workshop). PUT — создать или сохранить."""

    @extend_schema(tags=["shaper-cabinet"], responses=s.WorkshopCabinetSerializer,
                   parameters=[OpenApiParameter("organization", OpenApiTypes.UUID,
                                                description="Конкретная мастерская, если их несколько")])
    def get(self, request):
        membership = my_workshop_membership(request.user, request.query_params.get("organization"))
        if membership is None:
            raise NotFound("Мастерская ещё не создана.", code="no_workshop")
        workshop_service.ensure_workshop_profile(membership.organization)
        workshop = _reload_workshop(membership.organization_id)
        return Response(s.WorkshopCabinetSerializer(workshop, context={"request": request}).data)

    @extend_schema(tags=["shaper-cabinet"], request=s.WorkshopWriteSerializer,
                   responses={200: s.WorkshopCabinetSerializer, 201: s.WorkshopCabinetSerializer},
                   parameters=[OpenApiParameter("organization", OpenApiTypes.UUID,
                                                description="Конкретная мастерская, если их несколько")])
    def put(self, request):
        serializer = s.WorkshopWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = my_workshop_membership(request.user, request.query_params.get("organization"))
        workshop = None
        if membership is not None:
            workshop = member_workshop(request.user, membership.organization_id, manage=True)
        workshop, created = workshop_service.save_workshop(request.user, serializer.validated_data, workshop,
                                                           request=request)
        data = s.WorkshopCabinetSerializer(_reload_workshop(workshop.pk),
                                           context={"request": request, "created": created}).data
        return Response(data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class WorkshopPublishView(APIView):
    @extend_schema(tags=["shaper-cabinet"], request=None, responses=s.WorkshopCabinetSerializer,
                   summary="Опубликовать мастерскую: email подтверждён, заполнены название, регион, специализация")
    def post(self, request, pk):
        workshop = member_workshop(request.user, pk, manage=True)
        workshop_service.publish_workshop(request.user, workshop, request=request)
        return Response(s.WorkshopCabinetSerializer(_reload_workshop(pk), context={"request": request}).data)


class WorkshopUnpublishView(APIView):
    @extend_schema(tags=["shaper-cabinet"], request=None, responses=s.WorkshopCabinetSerializer,
                   summary="Снять мастерскую с публикации")
    def post(self, request, pk):
        workshop = member_workshop(request.user, pk, manage=True)
        workshop_service.unpublish_workshop(request.user, workshop, request=request)
        return Response(s.WorkshopCabinetSerializer(_reload_workshop(pk), context={"request": request}).data)


# ================================================================= кабинет: типы и материалы

@extend_schema_view(
    get=extend_schema(tags=["shaper-cabinet"], summary="Стандартные + свои типы мастерской (селект формы модели)"),
    post=extend_schema(tags=["shaper-cabinet"], request=s.BoardTypeWriteSerializer, responses={201: s.BoardTypeSerializer},
                       summary="Добавить свой тип доски (SHP-05, ATX-07)"),
)
class WorkshopBoardTypesView(generics.ListCreateAPIView):
    serializer_class = s.BoardTypeSerializer
    pagination_class = None

    def get_queryset(self):
        return type_service.types_for_workshop(member_workshop(self.request.user, self.kwargs["pk"]))

    def create(self, request, *args, **kwargs):
        workshop = member_workshop(request.user, kwargs["pk"])
        serializer = s.BoardTypeWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        board_type = type_service.create_board_type(workshop, serializer.validated_data)
        return Response(s.BoardTypeSerializer(board_type).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(tags=["shaper-cabinet"]),
    patch=extend_schema(tags=["shaper-cabinet"], request=s.BoardTypeWriteSerializer, responses=s.BoardTypeSerializer),
    delete=extend_schema(tags=["shaper-cabinet"], responses={204: None}),
)
class WorkshopBoardTypeDetailView(generics.GenericAPIView):
    serializer_class = s.BoardTypeSerializer

    def _object(self):
        workshop = member_workshop(self.request.user, self.kwargs["pk"])
        return type_service.custom_type(workshop, self.kwargs["type_id"])

    def get(self, request, *args, **kwargs):
        return Response(s.BoardTypeSerializer(self._object()).data)

    def patch(self, request, *args, **kwargs):
        board_type = self._object()
        serializer = s.BoardTypeWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(s.BoardTypeSerializer(type_service.update_board_type(board_type, serializer.validated_data)).data)

    def delete(self, request, *args, **kwargs):
        type_service.delete_board_type(self._object())
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    get=extend_schema(tags=["shaper-cabinet"], summary="Стандартные + свои материалы мастерской"),
    post=extend_schema(tags=["shaper-cabinet"], request=s.MaterialWriteSerializer, responses={201: s.MaterialSerializer},
                       summary="Добавить свой материал (SHP-05)"),
)
class WorkshopMaterialsView(generics.ListCreateAPIView):
    serializer_class = s.MaterialSerializer
    pagination_class = None

    def get_queryset(self):
        return type_service.materials_for_workshop(member_workshop(self.request.user, self.kwargs["pk"]))

    def create(self, request, *args, **kwargs):
        workshop = member_workshop(request.user, kwargs["pk"])
        serializer = s.MaterialWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        material = type_service.create_material(workshop, serializer.validated_data)
        return Response(s.MaterialSerializer(material).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(tags=["shaper-cabinet"]),
    patch=extend_schema(tags=["shaper-cabinet"], request=s.MaterialWriteSerializer, responses=s.MaterialSerializer),
    delete=extend_schema(tags=["shaper-cabinet"], responses={204: None}),
)
class WorkshopMaterialDetailView(generics.GenericAPIView):
    serializer_class = s.MaterialSerializer

    def _object(self):
        workshop = member_workshop(self.request.user, self.kwargs["pk"])
        return type_service.custom_material(workshop, self.kwargs["material_id"])

    def get(self, request, *args, **kwargs):
        return Response(s.MaterialSerializer(self._object()).data)

    def patch(self, request, *args, **kwargs):
        material = self._object()
        serializer = s.MaterialWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(s.MaterialSerializer(type_service.update_material(material, serializer.validated_data)).data)

    def delete(self, request, *args, **kwargs):
        type_service.delete_material(self._object())
        return Response(status=status.HTTP_204_NO_CONTENT)


# ================================================================= кабинет: модели

def _cabinet_model(model_id):
    return (BoardModel.objects.select_related("workshop", "board_type", "video")
            .prefetch_related(catalog.variant_prefetch(), catalog.media_prefetch()).get(pk=model_id))


def _detail_response(request, model_id, status_code=status.HTTP_200_OK):
    return Response(s.BoardModelCabinetDetailSerializer(_cabinet_model(model_id), context={"request": request}).data,
                    status=status_code)


CABINET_MODEL_FILTERS = [
    OpenApiParameter("status", str, description="draft | published | hidden | archived (по умолчанию все, кроме archived)"),
    OpenApiParameter("availability", str, description="in_stock | made_to_order | out_of_stock — вкладки «Мои доски»"),
    OpenApiParameter("board_type", str, description="Код типа"),
    OpenApiParameter("q", str, description="Название или артикул"),
]


@extend_schema_view(
    get=extend_schema(tags=["shaper-cabinet"], parameters=CABINET_MODEL_FILTERS, summary="«Мои доски» (BRD-01)"),
    post=extend_schema(tags=["shaper-cabinet"], request=s.BoardModelWriteSerializer,
                       responses={201: s.BoardModelCabinetDetailSerializer}, summary="Создать модель (черновик)"),
)
class WorkshopModelsView(generics.ListCreateAPIView):
    serializer_class = s.BoardModelCabinetSerializer

    def get_queryset(self):
        workshop = member_workshop(self.request.user, self.kwargs["pk"])
        params = self.request.query_params
        qs = BoardModel.objects.filter(workshop=workshop)
        if params.get("status"):
            qs = qs.filter(status__in=params["status"].split(","))
        else:
            qs = qs.exclude(status=BoardModel.Status.ARCHIVED)
        if params.get("board_type"):
            qs = qs.filter(board_type__code=params["board_type"])
        if params.get("q"):
            q = params["q"].strip()
            qs = qs.filter(Q(name__icontains=q) | Exists(BoardVariant.objects.filter(model=OuterRef("pk"),
                                                                                    sku__icontains=q)))
        qs = catalog.card_queryset(qs).order_by("-created_at")
        availability = params.get("availability")
        if availability == BoardVariant.Availability.IN_STOCK:
            qs = qs.filter(has_in_stock=True)
        elif availability == BoardVariant.Availability.MADE_TO_ORDER:
            qs = qs.filter(has_in_stock=False, has_made_to_order=True)
        elif availability == BoardVariant.Availability.OUT_OF_STOCK:
            qs = qs.filter(has_in_stock=False, has_made_to_order=False)
        return qs

    def create(self, request, *args, **kwargs):
        workshop = member_workshop(request.user, kwargs["pk"])
        serializer = s.BoardModelWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        model = model_service.create_model(workshop, request.user, serializer.validated_data, request=request)
        return _detail_response(request, model.pk, status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(tags=["shaper-cabinet"], responses=s.BoardModelCabinetDetailSerializer,
                      summary="Модель в кабинете (включая черновики)"),
    patch=extend_schema(tags=["shaper-cabinet"], request=s.BoardModelWriteSerializer,
                        responses=s.BoardModelCabinetDetailSerializer,
                        summary="Изменить модель; смена типа пересчитывает артикулы (с заказами — новые версии)"),
    delete=extend_schema(tags=["shaper-cabinet"], responses=s.DeletionResultSerializer,
                         summary="Удалить модель; при обращениях/экземплярах — архив (result=archived)"),
)
class ModelDetailView(generics.GenericAPIView):
    serializer_class = s.BoardModelCabinetDetailSerializer

    def _model(self):
        model = model_for_member(self.request.user, self.kwargs["model_id"])
        if "pk" in self.kwargs and str(model.workshop_id) != str(self.kwargs["pk"]):
            raise NotFound("Модель не найдена.", code="model_not_found")
        return model

    def get(self, request, *args, **kwargs):
        return _detail_response(request, self._model().pk)

    def patch(self, request, *args, **kwargs):
        model = self._model()
        serializer = s.BoardModelWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        if "variants" in data:
            raise DomainError("validation_error", "Варианты меняются через models/{id}/variants.",
                              fields={"variants": ["Недоступно при правке модели."]})
        model_service.update_model(model, request.user, data, request=request)
        return _detail_response(request, model.pk)

    def delete(self, request, *args, **kwargs):
        result = model_service.delete_model(self._model(), request.user, request=request)
        return Response({"result": result})


class ModelPublishView(APIView):
    @extend_schema(tags=["shaper-cabinet"], request=None, responses=s.BoardModelCabinetDetailSerializer,
                   summary="Опубликовать: ≥1 активный вариант, обложка, подтверждённый email")
    def post(self, request, model_id):
        model = model_for_member(request.user, model_id)
        model_service.publish_model(model, request.user, request=request)
        return _detail_response(request, model.pk)


class ModelUnpublishView(APIView):
    @extend_schema(tags=["shaper-cabinet"], request=None, responses=s.BoardModelCabinetDetailSerializer,
                   summary="Снять с публикации (черновик)")
    def post(self, request, model_id):
        model = model_for_member(request.user, model_id)
        model_service.unpublish_model(model, request.user, request=request)
        return _detail_response(request, model.pk)


# ================================================================= кабинет: медиа модели

def _media_payload(model):
    model = BoardModel.objects.select_related("video").get(pk=model.pk)
    items = list(BoardMedia.objects.filter(model=model).select_related("media").order_by("position", "id"))
    variants = {}
    for item in items:
        if item.variant_id:
            variants.setdefault(item.variant_id, []).append(item)
    return {
        "photos": s.BoardMediaSerializer([i for i in items if i.variant_id is None], many=True).data,
        "variants": [{"variant_id": vid, "photos": s.BoardMediaSerializer(v, many=True).data}
                     for vid, v in variants.items()],
        "video": s.MediaSerializer(model.video).data if model.video else None,
    }


def _variant_of(request, model, variant_id):
    return variant_for_member(request.user, model, variant_id) if variant_id else None


class ModelMediaView(APIView):
    @extend_schema(tags=["shaper-cabinet"], responses=s.BoardModelMediaSerializer, summary="Галереи модели и вариантов")
    def get(self, request, model_id):
        return Response(_media_payload(model_for_member(request.user, model_id)))

    @extend_schema(tags=["shaper-cabinet"], request=s.BoardMediaAddSerializer, responses={201: s.BoardModelMediaSerializer},
                   summary="Добавить фото (purpose board_photo); ≤10 на галерею → 409 photo_limit")
    def post(self, request, model_id):
        model = model_for_member(request.user, model_id)
        serializer = s.BoardMediaAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        variant = _variant_of(request, model, serializer.validated_data.get("variant_id"))
        media_service.add_photos(model, request.user, serializer.validated_data["media_ids"], variant=variant)
        return Response(_media_payload(model), status=status.HTTP_201_CREATED)


class ModelMediaOrderView(APIView):
    @extend_schema(tags=["shaper-cabinet"], request=s.BoardMediaOrderSerializer, responses=s.BoardModelMediaSerializer,
                   summary="Порядок фото галереи (первое — обложка)")
    def put(self, request, model_id):
        model = model_for_member(request.user, model_id)
        serializer = s.BoardMediaOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        variant = _variant_of(request, model, serializer.validated_data.get("variant_id"))
        media_service.reorder(model, serializer.validated_data["ids"], variant=variant)
        return Response(_media_payload(model))


class ModelMediaCoverView(APIView):
    @extend_schema(tags=["shaper-cabinet"], request=None, responses=s.BoardModelMediaSerializer,
                   summary="Сделать фото обложкой (переносится в начало галереи)")
    def post(self, request, model_id, item_id):
        model = model_for_member(request.user, model_id)
        media_service.set_cover(model, media_service.media_item(model, item_id))
        return Response(_media_payload(model))


class ModelMediaItemView(APIView):
    @extend_schema(tags=["shaper-cabinet"], responses=s.BoardModelMediaSerializer, summary="Удалить фото (×)")
    def delete(self, request, model_id, item_id):
        model = model_for_member(request.user, model_id)
        media_service.delete_photo(model, media_service.media_item(model, item_id))
        return Response(_media_payload(model))


class ModelVideoView(APIView):
    @extend_schema(tags=["shaper-cabinet"], request=s.BoardVideoSetSerializer, responses=s.BoardModelMediaSerializer,
                   summary="Отдельное видео доски (purpose board_video)")
    def put(self, request, model_id):
        model = model_for_member(request.user, model_id)
        serializer = s.BoardVideoSetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        media_service.set_video(model, request.user, serializer.validated_data["media_id"])
        return Response(_media_payload(model))

    @extend_schema(tags=["shaper-cabinet"], responses=s.BoardModelMediaSerializer, summary="Удалить видео доски")
    def delete(self, request, model_id):
        model = model_for_member(request.user, model_id)
        media_service.remove_video(model)
        return Response(_media_payload(model))


# ================================================================= кабинет: варианты

def _variant_qs():
    return BoardVariant.objects.select_related("material", "model", "model__board_type").annotate(
        items_available_for_sale=catalog.items_for_sale_count())


def _variant_response(request, variant_id, versioned=False, status_code=status.HTTP_200_OK):
    variant = _variant_qs().get(pk=variant_id)
    context = {"request": request, "versioned": versioned}
    return Response(s.VariantResultSerializer(variant, context=context).data, status=status_code)


@extend_schema_view(
    get=extend_schema(tags=["shaper-cabinet"], parameters=[
        OpenApiParameter("include_inactive", OpenApiTypes.BOOL, description="Показать прошлые версии/неактивные")],
        summary="Варианты модели"),
    post=extend_schema(tags=["shaper-cabinet"], request=s.VariantWriteSerializer,
                       responses={201: s.VariantResultSerializer},
                       summary="Создать вариант; артикул генерирует сервер, дубль → 409 sku_conflict (ATX-08)"),
)
class ModelVariantsView(generics.ListCreateAPIView):
    serializer_class = s.VariantCabinetSerializer
    pagination_class = None

    def get_queryset(self):
        model = model_for_member(self.request.user, self.kwargs["model_id"])
        qs = _variant_qs().filter(model=model).order_by("-is_active", "length_in", "width_in", "-version")
        include_inactive = str(self.request.query_params.get("include_inactive", "")).lower() in ("1", "true")
        return qs if include_inactive else qs.filter(is_active=True)

    def list(self, request, *args, **kwargs):
        variants = list(self.get_queryset())
        context = {**self.get_serializer_context(), "history_ids": variants_with_history([v.pk for v in variants])}
        return Response(s.VariantCabinetSerializer(variants, many=True, context=context).data)

    def create(self, request, *args, **kwargs):
        model = model_for_member(request.user, kwargs["model_id"])
        serializer = s.VariantWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        variant = variant_service.create_variant(model, request.user, serializer.validated_data, request=request)
        return _variant_response(request, variant.pk, status_code=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(tags=["shaper-cabinet"], responses=s.VariantResultSerializer),
    patch=extend_schema(tags=["shaper-cabinet"], request=s.VariantWriteSerializer, responses=s.VariantResultSerializer,
                        summary="Изменить вариант; размеры/материал/конструкция при заказах → новая версия (F10)"),
    delete=extend_schema(tags=["shaper-cabinet"], responses=s.DeletionResultSerializer,
                         summary="Удалить вариант; с историей или экземплярами — деактивация"),
)
class ModelVariantDetailView(generics.GenericAPIView):
    serializer_class = s.VariantResultSerializer

    def _variant(self):
        model = model_for_member(self.request.user, self.kwargs["model_id"])
        return variant_for_member(self.request.user, model, self.kwargs["variant_id"])

    def get(self, request, *args, **kwargs):
        return _variant_response(request, self._variant().pk)

    def patch(self, request, *args, **kwargs):
        variant = self._variant()
        serializer = s.VariantWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        variant, versioned = variant_service.update_variant(variant, request.user, serializer.validated_data,
                                                            request=request)
        return _variant_response(request, variant.pk, versioned=versioned)

    def delete(self, request, *args, **kwargs):
        return Response({"result": variant_service.delete_variant(self._variant(), request.user, request=request)})


class WorkshopVariantsView(generics.ListAPIView):
    serializer_class = s.VariantTableSerializer
    pagination_class = None

    @extend_schema(tags=["shaper-cabinet"], parameters=[
        OpenApiParameter("include_inactive", OpenApiTypes.BOOL, description="Включая прошлые версии")],
        summary="Все варианты мастерской для табличного редактора (BRD-12)")
    def get(self, request, *args, **kwargs):
        workshop = member_workshop(request.user, kwargs["pk"])
        qs = _variant_qs().filter(model__workshop=workshop).exclude(model__status=BoardModel.Status.ARCHIVED)
        if str(request.query_params.get("include_inactive", "")).lower() not in ("1", "true"):
            qs = qs.filter(is_active=True)
        variants = list(qs.order_by("model__name", "length_in", "width_in"))
        context = {"request": request, "history_ids": variants_with_history([v.pk for v in variants])}
        return Response(s.VariantTableSerializer(variants, many=True, context=context).data)


def _flatten_errors(errors, prefix=""):
    """{"items": [{}, {"price": ["…"]}]} → {"items.1.price": ["…"]} — ошибки строк таблицы с индексом."""
    flat = {}
    if isinstance(errors, dict):
        for key, value in errors.items():
            name = prefix if key == "non_field_errors" and prefix else (f"{prefix}.{key}" if prefix else key)
            flat.update(_flatten_errors(value, name))
    elif isinstance(errors, list) and any(isinstance(e, (dict, list)) for e in errors):
        for index, value in enumerate(errors):
            flat.update(_flatten_errors(value, f"{prefix}.{index}" if prefix else str(index)))
    elif errors:
        flat.setdefault(prefix or "non_field_errors", []).extend(
            str(e) for e in (errors if isinstance(errors, list) else [errors]))
    return flat


class WorkshopVariantsBulkView(APIView):
    @extend_schema(tags=["shaper-cabinet"], request=s.VariantBulkSerializer, responses=s.VariantBulkResultSerializer,
                   summary="Массовое изменение цены/срока/активности (всё или ничего)")
    def patch(self, request, pk):
        workshop = member_workshop(request.user, pk)
        serializer = s.VariantBulkSerializer(data=request.data)
        if not serializer.is_valid():
            raise DomainError("validation_error", "Проверьте значения в таблице.",
                              fields=_flatten_errors(serializer.errors))
        updated = variant_service.bulk_update_variants(workshop, request.user, serializer.validated_data["items"],
                                                       request=request)
        variants = list(_variant_qs().filter(pk__in=[v.pk for v in updated]).order_by("model__name", "length_in"))
        context = {"request": request, "history_ids": variants_with_history([v.pk for v in variants])}
        return Response({"updated": len(variants),
                         "items": s.VariantTableSerializer(variants, many=True, context=context).data})
