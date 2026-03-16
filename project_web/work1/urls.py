from django.urls import path
from . import views
from .views import ebay_form, get_category_fields, list_item


app_name = "work1"
urlpatterns = [
    path('', views.index, name='index'),  # ホームページ
    path('signup/', views.signup, name='signup'),  # サインアップページ

    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('callback/', views.callback, name='callback'),  # Redirect URL
    path('oauth/declined/', views.oauth_declined, name='oauth_declined'),

    path('update-ebay/', views.UpdateEbayView.as_view(), name='update_ebay'),

    path('update-scrapers/', views.UpdateScrapersView.as_view(), name='update_scrapers'),
    
    path('ebay_form/', ebay_form, name='ebay_form'),
    path('api/get-category-fields/', get_category_fields, name='get_category_fields'),
    path('list-item/', list_item, name='list_item'),
]