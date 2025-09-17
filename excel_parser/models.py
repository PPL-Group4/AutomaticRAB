from django.db import models

class RABItem(models.Model):
    number = models.CharField(max_length=50, blank=True)      # 'No' can be "1", "1.1", or alpha codes
    description = models.TextField()                           # 'Uraian Pekerjaan'
    volume = models.DecimalField(max_digits=20, decimal_places=4)
    unit = models.CharField(max_length=50)                     # 'Satuan'
    source_filename = models.CharField(max_length=255, blank=True)
    row_index = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["source_filename"])]