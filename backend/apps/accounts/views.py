"""accounts API (docs/ARCHITECTURE.md §3): тонкие представления — права → сервис → сериализатор."""
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, PolymorphicProxySerializer, extend_schema
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import serializers as s
from apps.accounts.models import Account, DataExportRequest, StaffRole
from apps.accounts.services import (
    consents,
    deletion,
    exports,
    profile as profile_service,
    public_profile,
    registration,
    specialties,
    staff,
    tokens,
    two_factor,
)
from apps.common.exceptions import DomainError, NotFound
from apps.common.permissions import IsPlatformAdmin

AUTH_TAG = ["auth"]
ME_TAG = ["me"]


def enforce_csrf(request):
    """CSRF и для анонимных POST (вход/регистрация): клиент сначала вызывает GET /auth/csrf (раздел 2)."""
    SessionAuthentication().enforce_csrf(request)


def me_payload(account, request):
    account = Account.objects.get(pk=account.pk)
    return s.MeSerializer(account, context={"request": request}).data


# --- auth ---------------------------------------------------------------------------------------------------

@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: s.CsrfSerializer}, tags=AUTH_TAG, summary="Выдать cookie csrftoken")
    def get(self, request):
        return Response({"csrf_token": get_token(request)})


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(request=s.RegisterSerializer, responses={201: s.RegisterResponseSerializer}, tags=AUTH_TAG,
                   summary="Регистрация (ATX-01)")
    def post(self, request):
        enforce_csrf(request)
        serializer = s.RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account, next_step = registration.register(**serializer.validated_data, request=request)
        data = dict(me_payload(account, request))
        data["next_step"] = next_step
        return Response(data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(request=s.LoginSerializer, responses={200: s.MeSerializer}, tags=AUTH_TAG, summary="Вход")
    def post(self, request):
        enforce_csrf(request)
        serializer = s.LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = registration.normalize_email(serializer.validated_data["email"])
        account = authenticate(request, email=email, password=serializer.validated_data["password"])
        if account is None or account.anonymized_at:
            raise DomainError("invalid_credentials", "Неверный email или пароль.")
        login(request, account)
        return Response(me_payload(account, request))


class LogoutView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={204: None}, tags=AUTH_TAG, summary="Выход")
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(request=s.EmailTokenSerializer, responses={200: s.EmailVerifiedSerializer}, tags=AUTH_TAG,
                   summary="Подтвердить email по ссылке из письма")
    def post(self, request):
        from apps.trust.services.audit import record

        serializer = s.EmailTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = tokens.read_email_token(serializer.validated_data["token"])
        if not account.is_email_verified:
            with transaction.atomic():
                account.email_verified_at = timezone.now()
                account.save(update_fields=["email_verified_at"])
                record(account, "account.email_verified", account, request=request)
        return Response({"email": account.email, "email_verified": True})


class VerifyEmailResendView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "auth"

    @extend_schema(request=None, responses={202: s.AccountsDetailSerializer}, tags=AUTH_TAG,
                   summary="Отправить письмо подтверждения повторно")
    def post(self, request):
        from apps.accounts.tasks import send_verification_email

        if request.user.is_email_verified:
            raise DomainError("already_verified", "Email уже подтверждён.")
        account_id = str(request.user.pk)
        transaction.on_commit(lambda: send_verification_email.delay(account_id))
        return Response({"detail": f"Письмо отправлено на {request.user.email}."}, status=status.HTTP_202_ACCEPTED)


class PasswordResetView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(request=s.PasswordResetRequestSerializer, responses={202: s.AccountsDetailSerializer}, tags=AUTH_TAG,
                   summary="Запросить ссылку для сброса пароля (ACC-13)")
    def post(self, request):
        from apps.accounts.tasks import send_password_reset_email

        enforce_csrf(request)
        serializer = s.PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = registration.normalize_email(serializer.validated_data["email"])
        account = Account.objects.filter(email__iexact=email, is_active=True, anonymized_at__isnull=True).first()
        if account is not None:
            account_id = str(account.pk)
            transaction.on_commit(lambda: send_password_reset_email.delay(account_id))
        # Ответ одинаковый для существующих и несуществующих адресов (нет перебора аккаунтов).
        return Response({"detail": "Если аккаунт с таким email существует, мы отправили письмо со ссылкой."},
                        status=status.HTTP_202_ACCEPTED)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(request=s.PasswordResetConfirmSerializer, responses={200: s.AccountsDetailSerializer}, tags=AUTH_TAG,
                   summary="Задать новый пароль по ссылке")
    def post(self, request):
        from apps.trust.services.audit import record

        enforce_csrf(request)
        serializer = s.PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        account = tokens.read_password_reset(data["uid"], data["token"])
        registration.validate_new_password(data["new_password"], account=account)
        with transaction.atomic():
            account.set_password(data["new_password"])
            fields = ["password"]
            if not account.is_email_verified:  # ссылка из письма подтверждает владение адресом
                account.email_verified_at = timezone.now()
                fields.append("email_verified_at")
            account.save(update_fields=fields)
            record(account, "account.password_reset", account, request=request)
        return Response({"detail": "Пароль изменён. Войдите с новым паролем."})


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "auth"

    @extend_schema(request=s.PasswordChangeSerializer, responses={200: s.AccountsDetailSerializer}, tags=AUTH_TAG,
                   summary="Сменить пароль")
    def post(self, request):
        from apps.trust.services.audit import record

        serializer = s.PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        account = request.user
        if not account.check_password(data["old_password"]):
            raise DomainError("password_incorrect", "Текущий пароль указан неверно.",
                              fields={"old_password": ["Неверный пароль."]})
        registration.validate_new_password(data["new_password"], account=account)
        with transaction.atomic():
            account.set_password(data["new_password"])
            account.save(update_fields=["password"])
            record(account, "account.password_changed", account, request=request)
        update_session_auth_hash(request, account)  # остальные сессии завершаются, текущая остаётся
        return Response({"detail": "Пароль изменён."})


class TwoFactorVerifyView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "auth"

    @extend_schema(request=s.TwoFactorCodeSerializer, responses={200: s.TwoFactorStateSerializer}, tags=AUTH_TAG,
                   summary="Подтвердить сессию TOTP-кодом")
    def post(self, request):
        serializer = s.TwoFactorCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        two_factor.verify_session(request.user, serializer.validated_data["code"], request)
        return Response(two_factor.state(request.user, request))


# --- /me ----------------------------------------------------------------------------------------------------

class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: s.MeSerializer}, tags=ME_TAG, summary="Мой аккаунт")
    def get(self, request):
        return Response(me_payload(request.user, request))

    @extend_schema(request=s.ProfileUpdateSerializer, responses={200: s.MeSerializer}, tags=ME_TAG,
                   summary="Изменить профиль")
    def patch(self, request):
        serializer = s.ProfileUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        profile_service.update_profile(request.user, serializer.validated_data, request=request)
        return Response(me_payload(request.user, request))


class MeSpecialtyView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: s.SpecialtyActivateResponseSerializer}, tags=ME_TAG,
                   summary="Подключить направление")
    def put(self, request, code):
        obj, next_step = specialties.activate_specialty(request.user, code, request=request)
        obj = type(obj).objects.select_related("specialty").get(pk=obj.pk)
        return Response({"specialty": s.UserSpecialtySerializer(obj).data, "next_step": next_step})

    @extend_schema(
        request=None,
        parameters=[OpenApiParameter("unpublish", OpenApiTypes.BOOL, required=False,
                                     description="Скрыть собственные публичные карточки (карточку инструктора)")],
        responses={200: s.SpecialtyDeactivateResponseSerializer}, tags=ME_TAG, summary="Отключить направление",
    )
    def delete(self, request, code):
        unpublish = str(request.query_params.get("unpublish", "")).lower() in {"1", "true", "yes"}
        obj, warnings, unpublished = specialties.deactivate_specialty(request.user, code, unpublish=unpublish,
                                                                      request=request)
        obj = type(obj).objects.select_related("specialty").get(pk=obj.pk)
        return Response({"specialty": s.UserSpecialtySerializer(obj).data, "warnings": warnings,
                         "unpublished": unpublished})


class TwoFactorSetupView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: s.TwoFactorSetupSerializer}, tags=ME_TAG,
                   summary="Новый TOTP-секрет")
    def post(self, request):
        return Response(two_factor.setup(request.user))


class TwoFactorEnableView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "auth"

    @extend_schema(request=s.TwoFactorCodeSerializer, responses={200: s.TwoFactorStateSerializer}, tags=ME_TAG,
                   summary="Включить 2FA")
    def post(self, request):
        serializer = s.TwoFactorCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        two_factor.enable(request.user, serializer.validated_data["code"], request)
        return Response(two_factor.state(request.user, request))


class TwoFactorDisableView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "auth"

    @extend_schema(request=s.TwoFactorCodeSerializer, responses={200: s.TwoFactorStateSerializer}, tags=ME_TAG,
                   summary="Отключить 2FA")
    def post(self, request):
        serializer = s.TwoFactorCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        two_factor.disable(request.user, serializer.validated_data["code"], request)
        return Response(two_factor.state(request.user, request))


class ConsentsView(APIView):
    permission_classes = [IsAuthenticated]

    def _payload(self, account):
        history = account.consents.order_by("-created_at", "-id")
        return {"current": consents.current_consents(account),
                "history": s.ConsentRecordSerializer(history, many=True).data}

    @extend_schema(responses={200: s.ConsentsResponseSerializer}, tags=ME_TAG, summary="Журнал согласий")
    def get(self, request):
        return Response(self._payload(request.user))

    @extend_schema(request=s.ConsentCreateSerializer, responses={201: s.ConsentsResponseSerializer}, tags=ME_TAG,
                   summary="Выдать или отозвать согласие")
    def post(self, request):
        serializer = s.ConsentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            consents.set_consent(request.user, serializer.validated_data["kind"],
                                 serializer.validated_data["granted"], request)
        return Response(self._payload(request.user), status=status.HTTP_201_CREATED)


class ExportsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: s.DataExportSerializer(many=True)}, tags=ME_TAG, summary="Мои выгрузки данных")
    def get(self, request):
        qs = DataExportRequest.objects.filter(account=request.user).select_related("file").order_by("-created_at")[:20]
        return Response(s.DataExportSerializer(qs, many=True).data)

    @extend_schema(request=None, responses={202: s.DataExportSerializer}, tags=ME_TAG,
                   summary="Запросить выгрузку данных (JSON)")
    def post(self, request):
        export = exports.request_export(request.user)
        return Response(s.DataExportSerializer(export).data, status=status.HTTP_202_ACCEPTED)


class DeletionView(APIView):
    permission_classes = [IsAuthenticated]

    def _payload(self, account):
        current = deletion.active_request(account)
        return {"pending": current is not None,
                "request": s.DeletionRequestSerializer(current).data if current else None,
                "grace_days": deletion.grace_days()}

    @extend_schema(responses={200: s.DeletionStateSerializer}, tags=ME_TAG, summary="Статус запроса на удаление")
    def get(self, request):
        return Response(self._payload(request.user))

    @extend_schema(request=s.DeletionCreateSerializer, responses={202: s.DeletionStateSerializer}, tags=ME_TAG,
                   summary="Запросить удаление аккаунта (AT-10)")
    def post(self, request):
        serializer = s.DeletionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        deletion.request_deletion(request.user, serializer.validated_data.get("reason", ""), request=request)
        return Response(self._payload(request.user), status=status.HTTP_202_ACCEPTED)

    @extend_schema(responses={200: s.DeletionStateSerializer}, tags=ME_TAG, summary="Отменить удаление")
    def delete(self, request):
        deletion.cancel_deletion(request.user, request=request)
        return Response(self._payload(request.user))


# --- публичный профиль --------------------------------------------------------------------------------------

class PublicProfileView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        responses={200: PolymorphicProxySerializer(
            component_name="PublicProfileOrRedirect",
            serializers=[s.UserPublicProfileSerializer, s.ProfileRedirectSerializer],
            resource_type_field_name=None,
        )},
        tags=["profiles"], summary="Публичный профиль (старый handle → {redirect})",
    )
    def get(self, request, handle):
        kind, value = public_profile.resolve(handle)
        if kind == "redirect":
            return Response({"redirect": value})
        return Response(s.UserPublicProfileSerializer(public_profile.build(value)).data)


# --- служебные роли -----------------------------------------------------------------------------------------

class StaffRolesView(APIView):
    permission_classes = [IsPlatformAdmin]

    @extend_schema(
        parameters=[OpenApiParameter("include_revoked", OpenApiTypes.BOOL, required=False),
                    OpenApiParameter("role", OpenApiTypes.STR, required=False, enum=StaffRole.Role.values)],
        responses={200: s.StaffRoleSerializer(many=True)}, tags=["staff"], summary="Служебные роли",
    )
    def get(self, request):
        qs = StaffRole.objects.select_related("account__profile", "granted_by__profile").order_by("-granted_at")
        if str(request.query_params.get("include_revoked", "")).lower() not in {"1", "true", "yes"}:
            qs = qs.filter(revoked_at__isnull=True)
        role = request.query_params.get("role")
        if role:
            qs = qs.filter(role=role)
        return Response(s.StaffRoleSerializer(qs, many=True).data)

    @extend_schema(request=s.StaffRoleGrantSerializer, responses={201: s.StaffRoleSerializer}, tags=["staff"],
                   summary="Выдать роль")
    def post(self, request):
        serializer = s.StaffRoleGrantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = staff.grant_role(request.user, serializer.validated_data["account_email"],
                                serializer.validated_data["role"], request=request)
        return Response(s.StaffRoleSerializer(role).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=s.StaffRoleRevokeSerializer, responses={200: s.StaffRoleSerializer}, tags=["staff"],
                   summary="Отозвать роль (по id или email + role)", operation_id="staff_roles_revoke")
    def delete(self, request):
        serializer = s.StaffRoleRevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        role_id = data.get("id")
        if not role_id:
            found = staff.find_active_role(data["account_email"], data["role"])
            if found is None:
                raise NotFound("Активная роль не найдена.")
            role_id = found.pk
        role = staff.revoke_role(request.user, role_id, request=request)
        return Response(s.StaffRoleSerializer(role).data)


class StaffRoleDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    @extend_schema(request=None, responses={200: s.StaffRoleSerializer}, tags=["staff"], summary="Отозвать роль",
                   operation_id="staff_roles_destroy")
    def delete(self, request, pk):
        role = staff.revoke_role(request.user, pk, request=request)
        return Response(s.StaffRoleSerializer(role).data)

