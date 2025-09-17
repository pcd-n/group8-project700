#allocation/models.py
from django.db import models
from django.conf import settings

class Allocation(models.Model):
    """
    Links a tutor to a timetable class slot.
    """
    session = models.ForeignKey(
        "timetable.TimeTable",
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    tutor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    preference = models.IntegerField(default=0)  # copy of coordinator preference
    status = models.CharField(
        max_length=50,
        choices=[("pending", "Pending"), ("completed", "Completed")],
        default="pending",
    )
    approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_allocations",
    )

    class Meta:
        unique_together = ("session", "tutor")

    def __str__(self):
        return f"{self.session} → {self.tutor}"
