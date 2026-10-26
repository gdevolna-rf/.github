from django.urls import path

from apps.trust import views

urlpatterns = [
    # отзывы
    path("reviews", views.ReviewListCreateView.as_view(), name="reviews"),
    path("reviews/<uuid:pk>", views.ReviewDeleteView.as_view(), name="review-delete"),
    path("me/reviews", views.MyReviewListView.as_view(), name="my-reviews"),
    # жалобы
    path("complaints", views.ComplaintCreateView.as_view(), name="complaints"),
    path("me/complaints", views.MyComplaintListView.as_view(), name="my-complaints"),
    path("complaints/<uuid:pk>/appeal", views.ComplaintAppealView.as_view(), name="complaint-appeal"),
    # модерация: очередь
    path("moderation/cases", views.CaseListView.as_view(), name="moderation-cases"),
    path("moderation/cases/<uuid:pk>", views.CaseDetailView.as_view(), name="moderation-case"),
    path("moderation/cases/<uuid:pk>/take", views.CaseTakeView.as_view(), name="moderation-case-take"),
    # модерация: решения
    path("moderation/proposals/<uuid:pk>/approve", views.ProposalApproveView.as_view()),
    path("moderation/proposals/<uuid:pk>/reject", views.ProposalRejectView.as_view()),
    path("moderation/proposals/<uuid:pk>/request-info", views.ProposalRequestInfoView.as_view()),
    path("moderation/proposals/<uuid:pk>/revert", views.ProposalRevertView.as_view()),
    path("moderation/reviews/<uuid:pk>/approve", views.ReviewApproveView.as_view()),
    path("moderation/reviews/<uuid:pk>/reject", views.ReviewRejectView.as_view()),
    path("moderation/reviews/<uuid:pk>/hide", views.ReviewHideView.as_view()),
    path("moderation/certificates/<uuid:pk>/approve", views.CertificateApproveView.as_view()),
    path("moderation/certificates/<uuid:pk>/reject", views.CertificateRejectView.as_view()),
    path("moderation/certificates/<uuid:pk>/revoke", views.CertificateRevokeView.as_view()),
    path("moderation/organizations/<uuid:pk>/approve", views.OrganizationApproveView.as_view()),
    path("moderation/organizations/<uuid:pk>/reject", views.OrganizationRejectView.as_view()),
    path("moderation/complaints/<uuid:pk>/resolve", views.ComplaintResolveView.as_view()),
    path("moderation/complaints/<uuid:pk>/dismiss", views.ComplaintDismissView.as_view()),
    path("moderation/complaints/<uuid:pk>/appeal-decision", views.ComplaintAppealDecisionView.as_view()),
    # модерация: аккаунты, журнал, статистика
    path("moderation/accounts/<uuid:pk>", views.ModerationAccountView.as_view(), name="moderation-account"),
    path("moderation/accounts/<uuid:pk>/restrict", views.AccountRestrictView.as_view(), name="moderation-restrict"),
    path("moderation/restrictions/<uuid:pk>/lift", views.RestrictionLiftView.as_view(), name="moderation-lift"),
    path("moderation/audit", views.AuditListView.as_view(), name="moderation-audit"),
    path("moderation/stats", views.ModerationStatsView.as_view(), name="moderation-stats"),
]
