from django.shortcuts import render


# Create your views here.

def index(request):
    return render(request, "vergihesapla/index.html")

def privacy_policy(request):
    return render(request, "vergihesapla/privacy_policy.html")