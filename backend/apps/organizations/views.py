"""organizations API (docs/ARCHITECTURE.md §3). Не участник → 404, участник без нужной роли → 403."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import Forbidden, NotFound
from apps.common.permissions import ReadOnlyOrAuthenticated
from apps.organizations import serializers as s
from apps.organizations.models import Membership, Organization, OrganizationInvite
from apps.organizations.services import invites as invite_service
from apps.organizations.services import members as member_service
from apps.organizations.services import organizations as org_service
from apps.organizations.services.access import MANAGE_ROLES

TAG = ["organizations"]


class OrganizationListCreateView(generics.ListAPIView):
    permission_classes = [ReadOnlyOrAuthenticated]
    serializer_class = s.OrganizationCardSerializer

    def get_queryset(self):
        return org_service.public_queryset(self.request.query_params)

    @extend_schema(
        parameters=[
            OpenApiParameter("kind", OpenApiTypes.STR, enum=Organization.Kind.values, required=False),
            OpenApiParameter("region", OpenApiTypes.STR, required=False, description="slug или id региона"),
            OpenApiParameter("spot", OpenApiTypes.STR, required=False, description="slug или id спота"),
            OpenApiParameter("q", OpenApiTypes.STR, required=False),
        ],
        tags=TAG, summary="Каталог опубликованных организаций",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(request=s.OrganizationWriteSerializer, responses={201: s.OrganizationManageSerializer}, tags=TAG,
                   summary="Создать организацию (создатель — владелец)")
    def post(self, request):
        serializer = s.OrganizationWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = org_service.create_organization(request.user, serializer.validated_data, request=request)
        return Response(s.OrganizationManageSerializer(org, context={"request": request}).data,
                        status=status.HTTP_201_CREATED)


class OrganizationPublicDetailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses={200: s.OrganizationPublicSerializer}, tags=TAG, summary="Публичная карточка организации")
    def get(self, request, slug):
        org = Organization.objects.select_related("region", "logo", "cover").filter(
            slug=slug, status=Organization.Status.PUBLISHED).first()
        if org is None:
            raise NotFound("Организация не найдена.")
        return Response(s.OrganizationPublicSerializer(org, context={"request": request}).data)


class MyOrganizationsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: s.MyOrganizationMembershipSerializer(many=True)}, tags=TAG, summary="Мои членства")
    def get(self, request):
        qs = Membership.objects.filter(account=request.user, status=Membership.Status.ACTIVE).select_related(
            "organization__region", "organization__logo", "organization__cover").order_by("joined_at")
        return Response(s.MyOrganizationMembershipSerializer(qs, many=True).data)


class OrganizationManageView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: s.OrganizationManageSerializer}, tags=TAG, summary="Закрытая карточка")
    def get(self, request, pk):
        org, _ = org_service.get_for_member(pk, request.user, MANAGE_ROLES)
        return Response(s.OrganizationManageSerializer(org, context={"request": request}).data)

    @extend_schema(request=s.OrganizationPatchSerializer, responses={200: s.OrganizationManageSerializer}, tags=TAG,
                   summary="Редактировать организацию")
    def patch(self, request, pk):
        org, _ = org_service.get_for_member(pk, request.user, MANAGE_ROLES)
        serializer = s.OrganizationPatchSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        org = org_service.update_organization(org, request.user, serializer.validated_data, request=request)
        org.refresh_from_db()
        return Response(s.OrganizationManageSerializer(org, context={"request": request}).data)


class OrganizationSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: s.OrganizationManageSerializer}, tags=TAG,
                   summary="Отправить на проверку перед публикацией (SCH-13)")
    def post(self, request, pk):
        org, _ = org_service.get_for_member(pk, request.user, (Membership.Role.OWNER,))
        org = org_service.submit_for_review(org, request.user, request=request)
        return Response(s.OrganizationManageSerializer(org, context={"request": request}).data)


class MembersView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[OpenApiParameter("status", OpenApiTypes.STR, required=False,
                                     enum=Membership.Status.values + ["all"],
                                     description="По умолчанию active; история — только owner/manager")],
        responses={200: s.OrganizationMembershipSerializer(many=True)}, tags=TAG, summary="Команда организации",
    )
    def get(self, request, pk):
        org, membership = org_service.get_for_member(pk, request.user)
        status_filter = request.query_params.get("status") or Membership.Status.ACTIVE
        qs = Membership.objects.filter(organization=org).select_related(
            "account__profile__avatar", "invited_by__profile", "revoked_by__profile").order_by("joined_at")
        if status_filter != Membership.Status.ACTIVE and membership.role not in MANAGE_ROLES:
            raise Forbidden("История команды доступна владельцу и менеджерам.")
        if status_filter != "all":
            qs = qs.filter(status=status_filter)
        return Response(s.OrganizationMembershipSerializer(qs, many=True).data)


class MemberDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=s.OrganizationMembershipUpdateSerializer, responses={200: s.OrganizationMembershipSerializer}, tags=TAG,
                   summary="Сменить роль/должность участника")
    def patch(self, request, pk, membership_id):
        org, membership = org_service.get_for_member(pk, request.user, MANAGE_ROLES)
        serializer = s.OrganizationMembershipUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = member_service.update_member(org, membership, membership_id, serializer.validated_data,
                                               request=request)
        return Response(s.OrganizationMembershipSerializer(updated).data)

    @extend_schema(responses={200: s.OrganizationMembershipSerializer}, tags=TAG,
                   summary="Отозвать доступ (немедленно; история сохраняется)")
    def delete(self, request, pk, membership_id):
        org, membership = org_service.get_for_member(pk, request.user, MANAGE_ROLES)
        revoked = member_service.revoke_member(org, membership, membership_id, request=request)
        return Response(s.OrganizationMembershipSerializer(revoked).data)


class OrganizationInvitesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[OpenApiParameter("status", OpenApiTypes.STR, required=False,
                                     enum=OrganizationInvite.Status.values + ["all"])],
        responses={200: s.OrganizationInviteSerializer(many=True)}, tags=TAG, summary="Приглашения организации",
    )
    def get(self, request, pk):
        org, _ = org_service.get_for_member(pk, request.user, MANAGE_ROLES)
        status_filter = request.query_params.get("status") or OrganizationInvite.Status.PENDING
        qs = OrganizationInvite.objects.filter(organization=org).select_related("invited_by__profile__avatar")
        if status_filter != "all":
            qs = qs.filter(status=status_filter)
        return Response(s.OrganizationInviteSerializer(qs.order_by("-created_at"), many=True).data)

    @extend_schema(request=s.OrganizationInviteCreateSerializer, responses={201: s.OrganizationInviteSerializer}, tags=TAG,
                   summary="Пригласить по email")
    def post(self, request, pk):
        org, membership = org_service.get_for_member(pk, request.user, MANAGE_ROLES)
        serializer = s.OrganizationInviteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invite = invite_service.create_invite(org, membership, request=request, **serializer.validated_data)
        return Response(s.OrganizationInviteSerializer(invite).data, status=status.HTTP_201_CREATED)


class InviteDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: s.OrganizationInviteSerializer}, tags=TAG, summary="Отозвать приглашение")
    def delete(self, request, pk):
        invite = invite_service.revoke_invite(pk, request.user, request=request)
        return Response(s.OrganizationInviteSerializer(invite).data)


class MyInvitesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: s.MyOrganizationInviteSerializer(many=True)}, tags=TAG, summary="Мои приглашения")
    def get(self, request):
        return Response(s.MyOrganizationInviteSerializer(invite_service.my_invites(request.user), many=True).data)


class InviteByTokenView(APIView):
    """GET /invites/{token}: карточка приглашения для страницы /invites/{token} (только адресату)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: s.MyOrganizationInviteSerializer}, tags=TAG, summary="Приглашение по токену")
    def get(self, request, token):
        invite = OrganizationInvite.objects.select_related("organization__logo", "invited_by__profile").filter(
            token=token).first()
        if invite is None:
            raise NotFound("Приглашение не найдено.")
        user = request.user
        if not (invite.account_id == user.pk or (invite.account_id is None
                                                 and invite.email.lower() == user.email.lower())):
            raise Forbidden("Приглашение адресовано другому аккаунту. Войдите под email, на который оно отправлено.",
                            code="invite_wrong_account")
        return Response(s.MyOrganizationInviteSerializer(invite).data)


class InviteAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: s.MyOrganizationMembershipSerializer}, tags=TAG, summary="Принять приглашение")
    def post(self, request, token):
        membership = invite_service.accept_invite(token, request.user, request=request)
        membership = Membership.objects.select_related("organization__region", "organization__logo",
                                                       "organization__cover").get(pk=membership.pk)
        return Response(s.MyOrganizationMembershipSerializer(membership).data)


class InviteDeclineView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: s.MyOrganizationInviteSerializer}, tags=TAG, summary="Отклонить приглашение")
    def post(self, request, token):
        invite = invite_service.decline_invite(token, request.user, request=request)
        return Response(s.MyOrganizationInviteSerializer(invite).data)


class TransferOwnershipView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=s.OrganizationTransferOwnershipSerializer, responses={200: s.OrganizationManageSerializer}, tags=TAG,
                   summary="Передать владение активному участнику")
    def post(self, request, pk):
        org, membership = org_service.get_for_member(pk, request.user, (Membership.Role.OWNER,))
        serializer = s.OrganizationTransferOwnershipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = member_service.transfer_ownership(org, membership, serializer.validated_data["account_id"],
                                                request=request)
        return Response(s.OrganizationManageSerializer(org, context={"request": request}).data)


class LeaveOrganizationView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None}, tags=TAG, summary="Покинуть организацию")
    def post(self, request, pk):
        org, _ = org_service.get_for_member(pk, request.user)
        member_service.leave(org, request.user, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)
