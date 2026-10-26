from django.urls import path

from apps.commerce import views

urlpatterns = [
    path("inquiries", views.InquiryListCreateView.as_view(), name="inquiries"),
    path("inquiries/<uuid:pk>", views.InquiryDetailView.as_view(), name="inquiry-detail"),
    path("inquiries/<uuid:pk>/accept", views.inquiry_accept, name="inquiry-accept"),
    path("inquiries/<uuid:pk>/decline", views.inquiry_decline, name="inquiry-decline"),
    path("inquiries/<uuid:pk>/complete", views.inquiry_complete, name="inquiry-complete"),
    path("inquiries/<uuid:pk>/cancel", views.inquiry_cancel, name="inquiry-cancel"),
    path("inquiries/<uuid:pk>/milestones", views.MilestoneListCreateView.as_view(), name="inquiry-milestones"),
    path("inquiries/<uuid:pk>/milestones/<uuid:milestone_id>", views.MilestoneDetailView.as_view(),
         name="inquiry-milestone"),
    path("milestones/<uuid:pk>/done", views.MilestoneDoneView.as_view(), name="milestone-done"),
    path("milestones/<uuid:pk>/confirm", views.MilestoneConfirmView.as_view(), name="milestone-confirm"),
    path("bookings", views.BookingListCreateView.as_view(), name="bookings"),
    path("bookings/<uuid:pk>", views.BookingDetailView.as_view(), name="booking-detail"),
    path("bookings/<uuid:pk>/confirm", views.booking_confirm, name="booking-confirm"),
    path("bookings/<uuid:pk>/decline", views.booking_decline, name="booking-decline"),
    path("bookings/<uuid:pk>/start", views.booking_start, name="booking-start"),
    path("bookings/<uuid:pk>/complete", views.booking_complete, name="booking-complete"),
    path("bookings/<uuid:pk>/no-show", views.booking_no_show, name="booking-no-show"),
    path("bookings/<uuid:pk>/cancel", views.booking_cancel, name="booking-cancel"),
]
