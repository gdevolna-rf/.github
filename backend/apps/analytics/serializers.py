from rest_framework import serializers

from apps.analytics.services.metrics import SCOPES
from apps.analytics.services.views import SUBJECT_EVENTS


class AnalyticsViewInputSerializer(serializers.Serializer):
    subject_type = serializers.ChoiceField(choices=sorted(SUBJECT_EVENTS))
    subject_id = serializers.CharField(max_length=80, help_text="UUID объекта; для instructor/surfer/spot/organization "
                                                               "допускается handle/slug")


class AnalyticsViewResultSerializer(serializers.Serializer):
    counted = serializers.BooleanField(help_text="false — бот, самопросмотр, сотрудник или повтор за сутки")
    event = serializers.CharField()
    subject_type = serializers.CharField()
    subject_id = serializers.CharField(help_text="Канонический UUID объекта")


class MetricsQuerySerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=SCOPES)
    organization_id = serializers.UUIDField(required=False)
    # from/to/tz разбираются resolve_period (даты YYYY-MM-DD включительно или ISO datetime)


class DashboardMetricSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    value = serializers.JSONField(help_text="int | float | строка-десятичное (деньги) | null (нет данных для формулы)")
    unit = serializers.ChoiceField(choices=["count", "percent", "money", "rating", "days", "minutes"])
    formula = serializers.CharField()
    currency = serializers.CharField(allow_null=True)


class MetricsPeriodSerializer(serializers.Serializer):
    def get_fields(self):
        return {
            "from": serializers.DateField(),
            "to": serializers.DateField(help_text="включительно"),
            "timezone": serializers.CharField(),
            "starts_at": serializers.DateTimeField(),
            "ends_at": serializers.DateTimeField(help_text="не включительно"),
        }


class MetricsResponseSerializer(serializers.Serializer):
    scope = serializers.CharField()
    period = MetricsPeriodSerializer()
    rule_version = serializers.IntegerField()
    generated_at = serializers.DateTimeField()
    subject = serializers.JSONField(help_text="{organizations: [{id, slug, name, kind}]} или {account: PublicAccount}")
    metrics = DashboardMetricSerializer(many=True)
    breakdowns = serializers.JSONField(help_text="Разбивки по разделу: см. описание эндпоинта")
