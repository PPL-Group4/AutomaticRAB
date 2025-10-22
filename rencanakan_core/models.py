from django.db import models

class Project(models.Model):
    id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=255)

    class Meta:
        db_table = "projects"
        managed = False

class Unit(models.Model):
    id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=100)

    class Meta:
        db_table = "units"
        managed = False

class ItemPrice(models.Model):
    id = models.CharField(primary_key=True, max_length=50)
    item_price_group_id = models.BigIntegerField(null=True)
    unit = models.ForeignKey(Unit, db_column="unit_id", null=True, on_delete=models.DO_NOTHING)
    type = models.CharField(max_length=50, null=True)   # e.g. 'ahs'
    name = models.CharField(max_length=255, null=True)

    class Meta:
        db_table = "item_prices"
        managed = False

class Ahs(models.Model):
    id = models.BigIntegerField(primary_key=True)
    reference_group_id = models.BigIntegerField(null=True)
    code = models.CharField(max_length=50, null=True)
    name = models.CharField(max_length=500, null=True)
    unit_price = models.DecimalField(max_digits=20, decimal_places=2, null=True)

    class Meta:
        db_table = "ahs"
        managed = False

class AhsItem(models.Model):
    id = models.BigIntegerField(primary_key=True)
    ahs = models.ForeignKey(Ahs, db_column="ahs_id", on_delete=models.DO_NOTHING)
    name = models.CharField(max_length=255, null=True)
    unit = models.ForeignKey(Unit, db_column="unit_id", null=True, on_delete=models.DO_NOTHING)
    coefficient = models.FloatField(default=0)
    section = models.CharField(max_length=20)  # 'labor','ingredients','tools','others'
    ahs_itemable_id = models.CharField(max_length=255)
    ahs_itemable_type = models.CharField(max_length=255)

    class Meta:
        db_table = "ahs_items"
        managed = False

    def resolve_item_price(self):
        if self.ahs_itemable_type == 'App\\Models\\ItemPrice':
            try:
                return ItemPrice.objects.get(id=self.ahs_itemable_id)
            except ItemPrice.DoesNotExist:
                return None
        return None

class Rab(models.Model):
    id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    project_id = models.BigIntegerField()

    class Meta:
        db_table = "rabs"
        managed = False

class RabItemHeader(models.Model):
    id = models.BigIntegerField(primary_key=True)
    rab = models.ForeignKey(Rab, db_column="rab_id", on_delete=models.DO_NOTHING)
    name = models.CharField(max_length=255, null=True)

    class Meta:
        db_table = "rab_item_headers"
        managed = False

class RabItem(models.Model):
    id = models.BigIntegerField(primary_key=True)
    rab = models.ForeignKey(Rab, db_column="rab_id", on_delete=models.DO_NOTHING, null=True)
    rab_item_header = models.ForeignKey(RabItemHeader, db_column="rab_item_header_id",
                                        on_delete=models.DO_NOTHING, null=True)
    name = models.CharField(max_length=500, null=True)  # free-text "uraian pekerjaan"
    custom_ahs_id = models.BigIntegerField(null=True)
    volume = models.FloatField(null=True)
    price = models.FloatField(null=True)
    unit = models.ForeignKey(Unit, db_column="unit_id", on_delete=models.DO_NOTHING, null=True)
    profit_margin = models.FloatField(null=True)

    class Meta:
        db_table = "rab_items"
        managed = False

class CustomAhs(models.Model):
    id = models.BigIntegerField(primary_key=True)
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=500)
    project_id = models.BigIntegerField()

    class Meta:
        db_table = "custom_ahs"
        managed = False

class CustomAhsItem(models.Model):
    id = models.BigIntegerField(primary_key=True)
    custom_ahs = models.ForeignKey(CustomAhs, db_column="custom_ahs_id", on_delete=models.DO_NOTHING)
    name = models.CharField(max_length=255, null=True)
    unit = models.ForeignKey(Unit, db_column="unit_id", null=True, on_delete=models.DO_NOTHING)
    coefficient = models.FloatField(default=0)
    section = models.CharField(max_length=20)  # labor / ingredients / tools / others
    custom_ahs_itemable_id = models.CharField(max_length=255)
    custom_ahs_itemable_type = models.CharField(max_length=255)

    class Meta:
        db_table = "custom_ahs_items"
        managed = False
