"""Маршруты learning (без префикса /api/v1/ и без завершающего слэша)."""
from django.urls import path

from apps.learning import views as v

urlpatterns = [
    # публичный каталог
    path("instructors", v.InstructorCatalogView.as_view(), name="instructor-list"),
    path("instructors/<slug:handle>", v.InstructorDetailView.as_view(), name="instructor-detail"),
    path("certificates/<uuid:pk>/scan", v.CertificateScanView.as_view(), name="certificate-scan"),
    # кабинет инструктора
    path("me/instructor", v.MyInstructorView.as_view(), name="my-instructor"),
    path("me/instructor/publish", v.PublishView.as_view(), name="my-instructor-publish"),
    path("me/instructor/unpublish", v.UnpublishView.as_view(), name="my-instructor-unpublish"),
    path("me/instructor/media", v.MyMediaView.as_view(), name="my-instructor-media"),
    path("me/instructor/media/<int:pk>", v.MyMediaItemView.as_view(), name="my-instructor-media-item"),
    path("me/instructor/certificates", v.MyCertificatesView.as_view(), name="my-certificates"),
    path("me/instructor/certificates/<uuid:pk>", v.MyCertificateDetailView.as_view(), name="my-certificate"),
    path("me/instructor/offers", v.MyOffersView.as_view(), name="my-offers"),
    path("me/instructor/offers/<uuid:pk>", v.MyOfferDetailView.as_view(), name="my-offer"),
    path("me/instructor/sessions", v.MySessionsView.as_view(), name="my-sessions"),
    path("me/instructor/sessions/<uuid:pk>", v.MySessionDetailView.as_view(), name="my-session"),
    path("me/schedule", v.MyScheduleView.as_view(), name="my-schedule"),
    path("me/students", v.MyStudentsView.as_view(), name="my-students"),
    # школа
    path("organizations/<uuid:org_id>/programs", v.OrgProgramsView.as_view(), name="org-programs"),
    path("organizations/<uuid:org_id>/programs/<uuid:pk>", v.OrgProgramDetailView.as_view(), name="org-program"),
    path("organizations/<uuid:org_id>/sessions", v.OrgSessionsView.as_view(), name="org-sessions"),
    path("organizations/<uuid:org_id>/sessions/<uuid:pk>", v.OrgSessionDetailView.as_view(), name="org-session"),
    path("organizations/<uuid:org_id>/students", v.OrgStudentsView.as_view(), name="org-students"),
    # занятие
    path("sessions/<uuid:pk>", v.SessionDetailView.as_view(), name="session-detail"),
    path("sessions/<uuid:pk>/assign", v.SessionAssignView.as_view(), name="session-assign"),
    path("sessions/<uuid:pk>/reschedule", v.SessionRescheduleView.as_view(), name="session-reschedule"),
    path("sessions/<uuid:pk>/cancel", v.SessionCancelView.as_view(), name="session-cancel"),
    path("sessions/<uuid:pk>/complete", v.SessionCompleteView.as_view(), name="session-complete"),
    path("sessions/<uuid:pk>/waitlist", v.SessionWaitlistView.as_view(), name="session-waitlist"),
    # заметки об учениках
    path("student-notes", v.StudentNotesView.as_view(), name="student-notes"),
    path("student-notes/<uuid:pk>", v.StudentNoteDetailView.as_view(), name="student-note"),
]
