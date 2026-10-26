from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("rentals", views.RentalListView.as_view(), name="rentals-list"),
    path("rentals/<uuid:pk>", views.RentalDetailView.as_view(), name="rentals-detail"),
    path("me/inventory", views.MyInventoryView.as_view(), name="me-inventory"),
    path("me/inventory/availability", views.MyInventoryAvailabilityView.as_view(), name="me-inventory-availability"),
    path("me/inventory/<uuid:pk>", views.MyInventoryItemView.as_view(), name="me-inventory-item"),
    path("me/inventory/<uuid:pk>/status", views.MyInventoryStatusView.as_view(), name="me-inventory-status"),
    path("me/inventory/<uuid:pk>/photos", views.MyInventoryPhotosView.as_view(), name="me-inventory-photos"),
    path("me/inventory/<uuid:pk>/photos/order", views.MyInventoryPhotoOrderView.as_view(),
         name="me-inventory-photos-order"),
    path("me/inventory/<uuid:pk>/photos/<int:photo_id>", views.MyInventoryPhotoView.as_view(),
         name="me-inventory-photo"),
    path("bookings/<uuid:pk>/handover", views.BookingHandoverView.as_view(), name="booking-handover"),
    path("bookings/<uuid:pk>/handovers", views.BookingHandoversView.as_view(), name="booking-handovers"),
]
