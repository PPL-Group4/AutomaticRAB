from __future__ import annotations
from decimal import Decimal
from django.db import models


class TestJob(models.Model):
    name = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "cw_jobs"


class TestItem(models.Model):
    job = models.ForeignKey(TestJob, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=255, blank=True, default="")
    cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    weight_pct = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        db_table = "cw_items"
