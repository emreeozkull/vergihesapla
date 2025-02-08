from django.contrib import admin
from .models import Calculator, CalculatorPDF
# Register your models here.

admin.site.register(Calculator)
admin.site.register(CalculatorPDF)

