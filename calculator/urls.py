from django.urls import path

from . import views

urlpatterns = [
    path('', views.calculator, name='calculator'),
    path('upload-pdf/', views.upload_pdf, name='upload_pdf'),
    path('results/', views.test_transactions, name='calculate_results'),
    path('api/create-calculator/', views.create_id_calculator, name='create_calculator'),
]
