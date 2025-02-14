from django.contrib import admin
from .models import Calculator, CalculatorPDF
# Register your models here.

class CalculatorAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'surname', 'email', 'phone', 'address', 'city', 'zip')
    list_filter = ('city', 'zip')
    search_fields = ('name', 'surname', 'email', 'phone', 'address', 'city', 'zip')
    list_per_page = 10


admin.site.register(Calculator, CalculatorAdmin)

class CalculatorPDFAdmin(admin.ModelAdmin):
    list_display = ('calculator', 'pdf', 'uploaded_at')
    list_filter = ('calculator__id',)
    search_fields = ('calculator__id', 'calculator__name')
    list_per_page = 25
    ordering = ('-calculator__id',)

admin.site.register(CalculatorPDF, CalculatorPDFAdmin)