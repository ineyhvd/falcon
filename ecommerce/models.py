from django.db import models
from decimal import Decimal
from django import forms
from phonenumber_field.modelfields import PhoneNumberField
import random
import string
import uuid


# Create your models here.


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    my_order = models.PositiveIntegerField(default=0, blank=False, null=False)

    class Meta:
        abstract = True


class Category(BaseModel):
    title = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['my_order']
        verbose_name = 'category'
        verbose_name_plural = "categories"


class Product(BaseModel):

    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    discount = models.PositiveIntegerField(default=0)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, related_name='products', null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1, null=True, blank=True)
    stock = models.BooleanField(default=False)
    favorite = models.BooleanField(default=False)

    @property
    def get_absolute_url(self):
        image = self.product_images.filter(is_primary=True).first()
        if image:
            return image.image.url
        return None

    @property
    def discounted_price(self):
        self.new_price = self.price
        if self.discount > 0:
            self.new_price = Decimal(self.price) * Decimal((1 - self.discount / 100))
        return Decimal(self.new_price).quantize(Decimal('0'))

    def __str__(self):
        return self.name

    def average_rating(self):
        comments = self.comments.all()
        if comments:
            return sum(comment.rating for comment in comments) / len(comments)
        return 0

    class Meta:
        ordering = ['my_order']
        verbose_name = 'product'
        verbose_name_plural = 'products'


class Image(BaseModel):
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, related_name='product_images', null=True,
                                blank=True)
    image = models.ImageField(upload_to='media/products/', null=True, blank=True)
    is_primary = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.image} => {self.is_primary}'


class Attribute(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class AttributeValue(models.Model):
    value = models.CharField(max_length=255)

    def __str__(self):
        return self.value


class ProductAttribute(models.Model):
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, related_name='product_attributes', null=True,
                                blank=True)
    attribute = models.ForeignKey(Attribute, on_delete=models.SET_NULL, null=True, blank=True)
    attribute_value = models.ForeignKey(AttributeValue, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.attribute.name


class Comment(BaseModel):
    full_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=255)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='comments')
    body = models.TextField()
    rating = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.full_name} - {self.product.name} ({self.rating}⭐)"

    class Meta:
        ordering = ['-created_at']


class Order(BaseModel):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]

    order_id = models.CharField(max_length=20, unique=True)
    date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    billing_address = models.TextField(default="No Billing Address")
    shipping_address = models.TextField(default="No Shipping Address")
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    payment_method = models.CharField(max_length=50)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def calculate_totals(self):
        self.subtotal = sum(
            item.quantity * item.product.discounted_price for item in self.order_items.all()
        )
        self.tax = (self.subtotal * Decimal(0.05)).quantize(Decimal('0.01'))
        self.total = self.subtotal + self.tax
        self.save()

    def __str__(self):
        return f"Order #{self.order_id}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"


def generate_random_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))


def generate_invoice_prefix():
    return ''.join(random.choices(string.ascii_uppercase, k=5))


class Customer(BaseModel):
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    description = models.TextField(blank=True, null=True, default="No Description")
    vat_number = models.CharField(max_length=50, blank=True, null=True, default="No VAT number")
    customer_image = models.ImageField(upload_to='media/customers/img',default='media/team/avatar.png')

    send_email_to = models.EmailField()
    address = models.TextField()
    phone_number = PhoneNumberField(region="UZ")
    invoice_prefix = models.CharField(max_length=5, default=generate_invoice_prefix, unique=True)
    invoice_number = models.IntegerField()

    @property
    def get_absolute_url(self):
        return self.customer_image.url

    def save(self, *args, **kwargs):
        if not self.invoice_prefix:
            self.invoice_prefix = generate_invoice_prefix()

        if not self.invoice_number:
            self.invoice_number = 1

        super().save(*args, **kwargs)

    def generate_invoice_id(self):
        return f"{self.invoice_prefix}-{self.invoice_number:05d}"

    def __str__(self):
        return f'{self.full_name} -> {self.generate_invoice_id()}'


class ShoppingCart(BaseModel):
    user = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='shopping_cart')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='shopping_cart')

    def get_total_price(self):
        return self.product.discounted_price

    def __str__(self):
        return f'{self.user} -> {self.product}'
