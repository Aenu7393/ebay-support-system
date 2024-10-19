from django.urls import path
from . import views

app_name = "work1"
urlpatterns=[
    path("",views.index,name="index")
]