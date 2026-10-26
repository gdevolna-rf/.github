from django.urls import path

from apps.organizations import views

urlpatterns = [
    path("organizations", views.OrganizationListCreateView.as_view(), name="organizations"),
    path("me/organizations", views.MyOrganizationsView.as_view(), name="me-organizations"),
    path("me/invites", views.MyInvitesView.as_view(), name="me-invites"),
    path("organizations/<uuid:pk>/manage", views.OrganizationManageView.as_view(), name="organization-manage"),
    path("organizations/<uuid:pk>/submit", views.OrganizationSubmitView.as_view(), name="organization-submit"),
    path("organizations/<uuid:pk>/members", views.MembersView.as_view(), name="organization-members"),
    path("organizations/<uuid:pk>/members/<uuid:membership_id>", views.MemberDetailView.as_view(),
         name="organization-member"),
    path("organizations/<uuid:pk>/invites", views.OrganizationInvitesView.as_view(), name="organization-invites"),
    path("organizations/<uuid:pk>/transfer-ownership", views.TransferOwnershipView.as_view(),
         name="organization-transfer"),
    path("organizations/<uuid:pk>/leave", views.LeaveOrganizationView.as_view(), name="organization-leave"),
    path("organizations/<slug:slug>", views.OrganizationPublicDetailView.as_view(), name="organization-public"),
    path("invites/<uuid:pk>", views.InviteDetailView.as_view(), name="invite-detail"),
    path("invites/<str:token>", views.InviteByTokenView.as_view(), name="invite-by-token"),
    path("invites/<str:token>/accept", views.InviteAcceptView.as_view(), name="invite-accept"),
    path("invites/<str:token>/decline", views.InviteDeclineView.as_view(), name="invite-decline"),
]
