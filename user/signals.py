from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from .models import User

@receiver(post_save, sender=User)
def after_user_saved(sender, instance, created, **kwargs):
    if created:
        print(f"New User created: {instance.name}")
    else:
        print(f"User updated: {instance}")

@receiver(pre_delete, sender=User)
def save_products_before_delete(sender, instance, **kwargs):
    with open("deleted_products.txt", "a") as file:
        file.write(f"O‘chirilgan user: {instance.name}\n")
    print(f"{instance.name} ma’lumotlari saqlandi va o‘chiriladi.")