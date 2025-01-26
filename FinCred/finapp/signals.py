from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Detail

User = get_user_model()

@receiver(post_save, sender=User)
def create_user_detail(sender, instance, created, **kwargs):
    """
    Automatically create a Detail record for each new user upon signup.
    """
    if created:
        Detail.objects.create(
            user=instance,
            income=0,
            savings=0,
            total_expenditure=0,
            housing=0,
            food=0,
            healthcare=0,
            transportation=0,
            recreation=0,
            others=0,
            stock=0,
            total_transactions=0
        )
