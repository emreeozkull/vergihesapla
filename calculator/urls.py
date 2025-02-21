from django.urls import path

from . import views

urlpatterns = [
    path('', views.calculator, name='calculator'),
    path('upload-pdf/', views.upload_pdf, name='upload_pdf'),
    path('results/', views.get_results, name='results'),
    path('api/create-calculator/', views.create_id_calculator, name='create_calculator'),
    path('test_calculation/<int:calculator_id>/', views.test_calculation, name='test_calculation'),
]
