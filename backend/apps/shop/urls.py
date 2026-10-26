from django.urls import path

from apps.shop import views

urlpatterns = [
    path("shop/products", views.ProductListView.as_view(), name="shop-products"),
    path("shop/products/<str:pk>/interest", views.ProductInterestView.as_view(), name="shop-product-interest"),
    path("shop/products/<str:slug>", views.ProductDetailView.as_view(), name="shop-product"),
]
