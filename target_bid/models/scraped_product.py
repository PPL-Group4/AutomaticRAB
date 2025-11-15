from django.db import models

class ScrapedProduct(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=500)
    price = models.IntegerField()
    unit = models.CharField(max_length=50)
    category = models.CharField(max_length=100)
    url = models.CharField(max_length=1000)
    location = models.CharField(max_length=200)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        abstract = True  

class JuraganMaterialProduct(ScrapedProduct):
    class Meta:
        managed = False
        db_table = "juragan_material_products"


class Mitra10Product(ScrapedProduct):
    class Meta:
        managed = False
        db_table = "mitra10_products"


class TokopediaProduct(ScrapedProduct):
    class Meta:
        managed = False
        db_table = "tokopedia_products"


class GemilangProduct(ScrapedProduct):
    class Meta:
        managed = False
        db_table = "gemilang_products"
