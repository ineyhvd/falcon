import csv
import json
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.urls import reverse_lazy
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse

from ecommerce.serializers import ProductSerializer, CategorySerializer
from ecommerce.utils import generate_invoice_prefix
from ecommerce.models import Product, Customer, ShoppingCart, Comment , Category
from ecommerce.forms import CustomerModelForm
from django.db.models import Max , Min , Count
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated , AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework import generics
from ecommerce.serializers import ProductSerializer



def index(request):
    search_query = request.GET.get('q', '')
    filter_type = request.GET.get('filter', '')
    products = Product.objects.all()

    if filter_type == 'date':
        products = Product.objects.all().order_by('-created_at')
    elif filter_type == 'name':
        products = Product.objects.all().order_by('name')
    elif filter_type == 'stock':
        products = Product.objects.all().order_by('-stock')
    elif filter_type == 'price_rating':
        products = Product.objects.all().order_by('-price', '-rating')

    if search_query:
        products = Product.objects.filter(name__icontains=search_query)

    paginator = Paginator(products, 4)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {'page_obj': page_obj, 'products': products}
    return render(request, 'ecommerce/product-list.html', context)


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    comments = Comment.objects.filter(product=product)
    context = {'product': product, 'comments': comments}
    return render(request, 'ecommerce/product-details.html', context)


def comment_view(request, pk):
    product = get_object_or_404(Product, id=pk)
    if request.method == "POST":
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        body = request.POST.get("body")
        rating = request.POST.get("rating") or 1

        Comment.objects.create(
            product=product, full_name=full_name, email=email, body=body, rating=int(rating)
        )

        messages.success(request, "Your review has been submitted successfully.")
        return redirect("ecommerce:product_detail", pk=product.id)

    return redirect("ecommerce:product_detail", pk=product.id)


def customer_list(request):
    filter_type = request.GET.get('filter', '')
    search_query = request.GET.get('q', '')
    customers = Customer.objects.all()

    if filter_type == 'filter':
        customers = customers.order_by('full_name')
    else:
        customers = customers.order_by('-created_at')

    for customer in customers:
        customer.created_date = customer.created_at.strftime("%B %d, %Y")

    if search_query:
        customers = customers.filter(full_name__icontains=search_query)

    context = {'customers': customers}
    return render(request, 'ecommerce/customers.html', context)


def customer_details(request, pk):
    customer = get_object_or_404(Customer, id=pk)
    created_date = customer.created_at.strftime("%b %d, %I:%M %p")
    context = {'customer': customer, 'created_date': created_date}
    return render(request, 'ecommerce/customer-details.html', context)


def add_customer(request):
    if request.method == "POST":
        form = CustomerModelForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.invoice_prefix = generate_invoice_prefix()
            customer.invoice_number = 1
            customer.save()
            return redirect('ecommerce:customer_list')
    else:
        form = CustomerModelForm()

    return render(request, 'ecommerce/add_customer.html', {'form': form})


def edit_customer(request, pk):
    customer = get_object_or_404(Customer, id=pk)
    if request.method == "POST":
        form = CustomerModelForm(request.POST, instance=customer)
        if form.is_valid():
            customer.save()
            return redirect('ecommerce:customer_list')
    else:
        form = CustomerModelForm(instance=customer)

    return render(request, 'ecommerce/edit_customer.html', {'form': form})


def delete_customer(request, pk):
    try:
        customer = Customer.objects.get(id=pk)
        customer.delete()
        return redirect('ecommerce:customer_list')
    except Customer.DoesNotExist:
        pass


def toggle_favourite(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.favorite = not product.favorite
    product.save()
    return JsonResponse({"favorite": product.favorite})


def view_cart(request):
    if request.user.is_authenticated:
        customer = get_object_or_404(Customer, email=request.user.email)
        cart_items = ShoppingCart.objects.filter(user=customer)
        total_price = sum(cart.get_total_price() for cart in cart_items)
    else:
        cart_items = None
        total_price = 0

    context = {'cart_items': cart_items, 'total_price': total_price}
    return render(request, 'ecommerce/shopping-cart.html', context)


def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.user.is_authenticated:
        customer, created = Customer.objects.get_or_create(
            email=request.user.email, defaults={'full_name': request.user.get_full_name()}
        )

        if ShoppingCart.objects.filter(user=customer, product=product).exists():
            messages.warning(request, "Bu mahsulot allaqachon savatchaga qo‘shilgan!")
        else:
            ShoppingCart.objects.create(user=customer, product=product)
            messages.success(request, "Mahsulot savatchaga qo‘shildi!")

    return redirect('ecommerce:index')


def remove_from_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.user.is_authenticated:
        customer = get_object_or_404(Customer, email=request.user.email)
        cart_item = ShoppingCart.objects.filter(user=customer, product=product).first()
        if cart_item:
            cart_item.delete()
            messages.success(request, "Mahsulot savatchadan o‘chirildi!")
        else:
            messages.warning(request, "Bu mahsulot savatchada topilmadi!")
    else:
        messages.warning(request, "Iltimos, avval tizimga kiring.")

    return redirect('ecommerce:shopping_cart')


def order_list(request):
    return render(request, 'ecommerce/order-list.html')


def export_data(request):
    format = request.GET.get('format', '')
    response = None
    if format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=customer_list.csv'
        writer = csv.writer(response)
        writer.writerow(['Id', 'Full Name', 'Email', 'Phone Number', 'Address'])
        for customer in Customer.objects.all():
            writer.writerow([customer.id, customer.full_name, customer.email, customer.phone_number, customer.address])
    elif format == 'json':
        response = HttpResponse(content_type='application/json')
        data = list(Customer.objects.all().values('full_name', 'email', 'address', 'phone_number'))
        for customer in data:
            customer['phone_number'] = str(customer['phone_number'])
        response.write(json.dumps(data, indent=3))
        response['Content-Disposition'] = 'attachment; filename=customers.json'
    elif format == 'xlsx':
        response = HttpResponse(content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename=customers.xlsx'
        writer = xlsx.writer(response)
        writer.writerow(['Id', 'Full Name', 'Email', 'Phone Number', 'Address'])
        for customer in Customer.objects.all():
            writer.writerow([customer.id, customer.full_name, customer.email, customer.phone_number, customer.address])


    else:
        response = HttpResponse(status=404)
        response.content = 'Bad request'

    return response


# (.venv) PS C:\Users\user\Desktop\ecommerce> py manage.py shell
# Python 3.13.2 (tags/v3.13.2:4f8bb39, Feb  4 2025, 15:23:48) [MSC v.1942 64 bit (AMD64)] on win32
# Type "help", "copyright", "credits" or "license" for more information.
# (InteractiveConsole)
# >>> from django.db.models import Max , Min , Count
# >>> from ecommerce.models import Order
# >>> Order.object.all().aggregate(Count('id'))
# Traceback (most recent call last):
#   File "<console>", line 1, in <module>
# AttributeError: type object 'Order' has no attribute 'object'. Did you mean: 'objects'?
# >>> Order.objects.all().aggregate(Count('id'))
# {'id__count': 0}





# (.venv) PS C:\Users\user\Desktop\ecommerce> py manage.py shell
# Python 3.13.2 (tags/v3.13.2:4f8bb39, Feb  4 2025, 15:23:48) [MSC v.1942 64 bit (AMD64)] on win32
# Type "help", "copyright", "credits" or "license" for more information.
# (InteractiveConsole)
# >>> from django.db.models import Max,Min,Count
# >>> from ecommerce.models import Order
# >>> Order.objects.all().annotade(avg_order_id=Avg('id'))
# Traceback (most recent call last):
#   File "<console>", line 1, in <module>
# AttributeError: 'QuerySet' object has no attribute 'annotade'. Did you mean: 'annotate'?
# >>> Order.objects.all().annotate(avg_order_id=Avg('id'))
# Traceback (most recent call last):
#   File "<console>", line 1, in <module>
# NameError: name 'Avg' is not defined
# >>> Order.objects.all().annotate(avg_order_id=Min('id'))
# <QuerySet []>

# class PostListOrCreate(APIView):
#     permission_classes = [AllowAny]
#
#     def get(self, request, format=None):
#         posts = Product.objects.all()
#         serializers = ProductSerializer(posts, many=True)
#
#         return Response(serializers.data, status=status.HTTP_200_OK)
#
#     def post(self, request):
#         serializer = ProductSerializer(data=request.data)
#         if serializer.is_valid():
#             serializer.save()
#             return Response(serializer.data, status=status.HTTP_201_CREATED)
#
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#
#
# class PostDetail(APIView):
#     def get(self, request, pk, format=None):
#         try:
#             post = Product.objects.get(id=pk)
#             serializer = ProductSerializer(post)
#             return Response(serializer.data)
#         except Product.DoesNotExist:
#             return Response({'error': 'Post does not exist'}, status=status.HTTP_404_NOT_FOUND)
#
#     def delete(self, request, pk=None):
#         try:
#             post = Product.objects.get(id=pk)
#             if post:
#                 post.delete()
#                 data = {'message': 'Post successfully deleted'}
#                 return Response(data, status=status.HTTP_204_NO_CONTENT)
#         except Product.DoesNotExist:
#             data = {'message': 'Post Not Found'}
#             return Response(data, status=status.HTTP_404_NOT_FOUND)
#
#     def put(self, request, pk=None):
#         post = Product.objects.get(pk=pk)
#         serializer = ProductSerializer(post, data=request.data)
#         if serializer.is_valid():
#             serializer.save()
#             return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#
#     def patch(self, request):
#         post = Product.objects.get(pk=pk)
#         serializer = ProductSerializer(post, data=request.data, partial=True)
#         if serializer.is_valid():
#             serializer.save()
#             return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class CategoryListCreateView(generics.GenericAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get(self, request, *args, **kwargs):
        category = self.get_queryset()
        serializer = self.get_serializer(category, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

class CategoryDetailView(generics.GenericAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get(self, request, pk, *args, **kwargs):
        try:
            category = self.get_object()
            serializer = self.get_serializer(category)
            return Response(serializer.data)
        except Category.DoesNotExist:
            return Response({"error": "Category topilmadi"}, status=404)

    def put(self, request, pk, *args, **kwargs):
        try:
            category = self.get_object()
            serializer = self.get_serializer(category, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=400)
        except Category.DoesNotExist:
            return Response({"error": "Category topilmadi"}, status=404)

    def delete(self, request, pk, *args, **kwargs):
        try:
            category = self.get_object()
            category.delete()
            return Response(status=204)
        except Category.DoesNotExist:
            return Response({"error": "Category topilmadi"}, status=404)




class ProductListCreateView(generics.GenericAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer


    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

class ProductDetailView(generics.GenericAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

    def get(self, request, pk, *args, **kwargs):
        try:
         product = self.get_queryset()
         serializer = self.get_serializer(product, many=True)
         return Response(serializer.data)
        except Product.DoesNotExist:
            return Response({"error": "Product topilmadi"}, status=404)

    def put(self, request, pk, *args, **kwargs):
        try:
            product = self.get_object()
            serializer = self.get_serializer(product, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=400)
        except Product.DoesNotExist:
            return Response({"error": "Product topilmadi"}, status=404)

    def delete(self, request, pk, *args, **kwargs):
        try:
            product = self.get_object()
            product.delete()
            return Response(status=204)
        except Product.DoesNotExist:
            return Response({"error": "Product topilmadi"}, status=404)

