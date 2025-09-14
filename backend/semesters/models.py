from django.db import models

class Semester(models.Model):
    TERM_CHOICES = [
        ("S1", "Semester 1"),
        ("S2", "Semester 2"),
        ("S3", "Semester 3"),
        ("S4", "Semester 4"),
    ]
    alias = models.SlugField(unique=True, help_text="Django DB alias, e.g. sem_2025_s2")
    db_name = models.CharField(max_length=128, unique=True, help_text="MySQL database name")
    year = models.PositiveIntegerField()
    term = models.CharField(max_length=10, choices=TERM_CHOICES)
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-year", "-created_at"]

    def __str__(self):
        c = " (current)" if self.is_current else ""
        return f"{self.year} {self.term}{c}"
