from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from .models import Product

@receiver(post_save, sender=Product)
def after_product_saved(sender, instance, created, **kwargs):
    if created:
        print(f"New product created: {instance}")
    else:
        print(f"Product updated: {instance}")

@receiver(pre_delete, sender=Product)
def save_products_before_delete(sender, instance, **kwargs):
    with open("deleted_products.txt.txt", "a") as file:
        file.write(f"O‘chirilgan product: {instance.name}, {instance.description}\n")
    print(f"{instance.name} ma’lumotlari saqlandi va o‘chiriladi.")