from django.urls import path

from apps.spots import views

urlpatterns = [
    path("regions", views.RegionListView.as_view(), name="regions"),
    path("spots", views.SpotListView.as_view(), name="spots"),
    path("spots/map", views.SpotMapView.as_view(), name="spots-map"),
    path("spots/dictionaries", views.SpotDictionariesView.as_view(), name="spots-dictionaries"),
    path("spots/<uuid:pk>/proposals", views.SpotProposalCreateView.as_view(), name="spot-proposals"),
    path("spots/<slug:slug>/forecast", views.SpotForecastView.as_view(), name="spot-forecast"),
    path("spots/<slug:slug>", views.SpotDetailView.as_view(), name="spot-detail"),
    path("me/proposals", views.MyProposalListView.as_view(), name="my-proposals"),
    path("proposals/<uuid:pk>", views.ProposalDetailView.as_view(), name="proposal-detail"),
    path("proposals/<uuid:pk>/withdraw", views.ProposalWithdrawView.as_view(), name="proposal-withdraw"),
]
