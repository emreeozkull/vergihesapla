from django.shortcuts import render


# Create your views here.

def index(request):
    return render(request, "vergihesapla/index.html")

def calculator(request):
    return render(request,"vergihesapla/calculator.html")