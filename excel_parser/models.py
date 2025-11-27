
from django.db import models


class Project(models.Model):
    """
    Holds all the high-level metadata for a single RAB project,
    extracted from the document's header section.
    """
    program = models.CharField(max_length=255, help_text="The overarching program name")
    kegiatan = models.CharField(max_length=255, help_text="The specific activity within the program")
    pekerjaan = models.CharField(max_length=255, help_text="The detailed name of the job or work")
    lokasi = models.CharField(max_length=255, help_text="The physical location of the project")
    tahun_anggaran = models.PositiveIntegerField(help_text="The fiscal year of the project")
    source_filename = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.pekerjaan} ({self.tahun_anggaran})"

class RabEntry(models.Model):
    """
    Represents a single row within a RAB project. This can be a section
    header, a work item with costs, a subtotal, or a grand total.
    """
    
    class EntryType(models.TextChoices):
        SITE_HEADER = 'SITE', 'Site Header'
        SECTION = 'SECTION', 'Section'
        SUB_SECTION = 'SUB_SECTION', 'Sub-Section'
        ITEM = 'ITEM', 'Work Item'
        SUB_TOTAL = 'SUB_TOTAL', 'Sub Total'
        GRAND_TOTAL = 'GRAND_TOTAL', 'Grand Total'

    entry_type = models.CharField(
        max_length=20,
        choices=EntryType.choices,
        help_text="The classification of this row (e.g., Section, Work Item, Sub Total)"
    )
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='entries')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    
    item_number = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField()
    unit = models.CharField(max_length=50, blank=True, null=True)
    analysis_code = models.CharField(max_length=50, blank=True, null=True)
    volume = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    unit_price = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    total_price = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    total_price_in_words = models.TextField(blank=True, null=True)
    row_index = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = "RAB Entries"
        ordering = ['id']

    def __str__(self):
        return f"({self.get_entry_type_display()}) {self.description[:60]}"