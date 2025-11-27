from __future__ import annotations

from decimal import Decimal

from django.db import models


class TestJob(models.Model):
    name = models.CharField(max_length=255, blank=True, default="")
    total_cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    excel_file = models.FileField(upload_to='rab_excel/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        db_table = "cw_jobs"

    def calculate_totals(self):
        """Calculate total cost and auto-assign weight percentages"""
        total = sum(item.cost for item in self.items.all())
        self.total_cost = total
        self.save()
        
        # Auto calculate weight percentages
        for item in self.items.all():
            if total > 0:
                item.weight_pct = (item.cost / total) * 100
                item.save()


class TestItem(models.Model):
    job = models.ForeignKey(TestJob, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=255, blank=True, default="")
    cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    weight_pct = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1"))
    unit_price = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))

    class Meta:
        db_table = "cw_items"

    def save(self, *args, **kwargs):
        """Auto calculate cost from quantity * unit_price"""
        self.cost = self.quantity * self.unit_price
        super().save(*args, **kwargs)
