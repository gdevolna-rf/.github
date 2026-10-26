from django.urls import path

from apps.accounts import views

urlpatterns = [
    path("auth/csrf", views.CsrfView.as_view(), name="auth-csrf"),
    path("auth/register", views.RegisterView.as_view(), name="auth-register"),
    path("auth/login", views.LoginView.as_view(), name="auth-login"),
    path("auth/logout", views.LogoutView.as_view(), name="auth-logout"),
    path("auth/verify-email", views.VerifyEmailView.as_view(), name="auth-verify-email"),
    path("auth/verify-email/resend", views.VerifyEmailResendView.as_view(), name="auth-verify-email-resend"),
    path("auth/password-reset", views.PasswordResetView.as_view(), name="auth-password-reset"),
    path("auth/password-reset/confirm", views.PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
    path("auth/password-change", views.PasswordChangeView.as_view(), name="auth-password-change"),
    path("auth/2fa/verify", views.TwoFactorVerifyView.as_view(), name="auth-2fa-verify"),
    path("me", views.MeView.as_view(), name="me"),
    path("me/specialties/<str:code>", views.MeSpecialtyView.as_view(), name="me-specialty"),
    path("me/2fa/setup", views.TwoFactorSetupView.as_view(), name="me-2fa-setup"),
    path("me/2fa/enable", views.TwoFactorEnableView.as_view(), name="me-2fa-enable"),
    path("me/2fa/disable", views.TwoFactorDisableView.as_view(), name="me-2fa-disable"),
    path("me/consents", views.ConsentsView.as_view(), name="me-consents"),
    path("me/exports", views.ExportsView.as_view(), name="me-exports"),
    path("me/deletion", views.DeletionView.as_view(), name="me-deletion"),
    path("profiles/<str:handle>", views.PublicProfileView.as_view(), name="public-profile"),
    path("staff/roles", views.StaffRolesView.as_view(), name="staff-roles"),
    path("staff/roles/<int:pk>", views.StaffRoleDetailView.as_view(), name="staff-role-detail"),
]
