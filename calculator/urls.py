from django.urls import path

from . import views

urlpatterns = [
    path('', views.calculator, name='calculator'),
    path('upload-pdf/', views.upload_pdf, name='upload_pdf'),
    path('results/', views.calculate_results, name='calculate_results'),
]
