from django.db import models


class UnmatchedAhsEntry(models.Model):
    """
    Stores job descriptions that couldn't be matched to any AHS code.
    Allows admins to manually assign AHS codes later.
    """
    name = models.CharField(max_length=255, unique=True)  # The job description from RAB file
    ahs_code = models.CharField(max_length=50, blank=True, default='')  # To be filled by admin
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "unmatched_ahs_entries"
        indexes = [
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.name[:50]}... - AHS: {self.ahs_code or 'Not assigned'}"