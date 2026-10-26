"""Поля сериализаторов, общие для apps.spots и apps.trust: значения справочников отдаются как {code, label}."""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


class ChoiceValueSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()


class CompassPointSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()
    short = serializers.CharField()
    degrees = serializers.FloatField(allow_null=True)


class MonthSerializer(serializers.Serializer):
    code = serializers.IntegerField()
    label = serializers.CharField()


@extend_schema_field(ChoiceValueSerializer(allow_null=True))
class LabeledChoiceField(serializers.Field):
    """Только для чтения: "beginner" → {"code": "beginner", "label": "Для новичков"}."""

    def __init__(self, choices, **kwargs):
        self.labels = dict(choices)
        kwargs["read_only"] = True
        super().__init__(**kwargs)

    def to_representation(self, value):
        if value in (None, ""):
            return None
        return {"code": value, "label": str(self.labels.get(value, value))}


def choice_dict(value, choices):
    if value in (None, ""):
        return None
    return {"code": value, "label": str(dict(choices).get(value, value))}
