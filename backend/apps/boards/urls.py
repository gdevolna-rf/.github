from django.urls import path

from apps.boards import views

urlpatterns = [
    # Публичный каталог (all)
    path("boards", views.BoardListView.as_view(), name="boards-list"),
    path("boards/<uuid:pk>", views.BoardDetailView.as_view(), name="boards-detail"),
    path("board-types", views.PublicBoardTypesView.as_view(), name="board-types"),
    path("board-materials", views.PublicMaterialsView.as_view(), name="board-materials"),
    path("shapers", views.ShaperListView.as_view(), name="shapers-list"),
    path("shapers/<slug:slug>", views.ShaperDetailView.as_view(), name="shapers-detail"),
    path("shapers/<slug:slug>/boards", views.ShaperBoardsView.as_view(), name="shapers-boards"),
    # Кабинет шейпера
    path("me/workshop", views.MyWorkshopView.as_view(), name="me-workshop"),
    path("workshops/<uuid:pk>/publish", views.WorkshopPublishView.as_view(), name="workshop-publish"),
    path("workshops/<uuid:pk>/unpublish", views.WorkshopUnpublishView.as_view(), name="workshop-unpublish"),
    path("workshops/<uuid:pk>/board-types", views.WorkshopBoardTypesView.as_view(), name="workshop-board-types"),
    path("workshops/<uuid:pk>/board-types/<int:type_id>", views.WorkshopBoardTypeDetailView.as_view(),
         name="workshop-board-type"),
    path("workshops/<uuid:pk>/materials", views.WorkshopMaterialsView.as_view(), name="workshop-materials"),
    path("workshops/<uuid:pk>/materials/<int:material_id>", views.WorkshopMaterialDetailView.as_view(),
         name="workshop-material"),
    path("workshops/<uuid:pk>/models", views.WorkshopModelsView.as_view(), name="workshop-models"),
    path("workshops/<uuid:pk>/models/<uuid:model_id>", views.ModelDetailView.as_view(), name="workshop-model"),
    path("workshops/<uuid:pk>/variants", views.WorkshopVariantsView.as_view(), name="workshop-variants"),
    path("workshops/<uuid:pk>/variants/bulk", views.WorkshopVariantsBulkView.as_view(), name="workshop-variants-bulk"),
    path("models/<uuid:model_id>", views.ModelDetailView.as_view(), name="model-detail"),
    path("models/<uuid:model_id>/publish", views.ModelPublishView.as_view(), name="model-publish"),
    path("models/<uuid:model_id>/unpublish", views.ModelUnpublishView.as_view(), name="model-unpublish"),
    path("models/<uuid:model_id>/media", views.ModelMediaView.as_view(), name="model-media"),
    path("models/<uuid:model_id>/media/order", views.ModelMediaOrderView.as_view(), name="model-media-order"),
    path("models/<uuid:model_id>/media/<int:item_id>", views.ModelMediaItemView.as_view(), name="model-media-item"),
    path("models/<uuid:model_id>/media/<int:item_id>/cover", views.ModelMediaCoverView.as_view(),
         name="model-media-cover"),
    path("models/<uuid:model_id>/video", views.ModelVideoView.as_view(), name="model-video"),
    path("models/<uuid:model_id>/variants", views.ModelVariantsView.as_view(), name="model-variants"),
    path("models/<uuid:model_id>/variants/<uuid:variant_id>", views.ModelVariantDetailView.as_view(),
         name="model-variant"),
]
