from django.db import models

# Create your models here.


class Calculator(models.Model):
    id = models.AutoField(primary_key=True, unique=True)
    name = models.CharField(max_length=200)
    surname = models.CharField(max_length=200)
    email = models.EmailField(max_length=200)
    phone = models.CharField(max_length=200)
    address = models.CharField(max_length=200)
    city = models.CharField(max_length=200)
    zip = models.CharField(max_length=200)

    customer_name = models.CharField(max_length=200, null=True, blank=True)
    tckn = models.PositiveBigIntegerField(null=True, blank=True)
    account_opening_date = models.DateTimeField(null=True, blank=True)
    
    is_paid = models.BooleanField(default=False)
    is_calculated = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.id} - {self.name} {self.surname}" 
    

    
def get_upload_path(instance, filename):
    # instance.calculator.id will give us the calculator's ID
    return f'pdfs/{instance.calculator.id}/{filename}'

class CalculatorPDF(models.Model):
    calculator = models.ForeignKey(Calculator, on_delete=models.CASCADE)
    pdf = models.FileField(upload_to=get_upload_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    #account_info = models.JSONField(null=True, blank=True) #{'customer_name': '', 'tckn': '', 'account_opening_date': [datetime.datetime(2022, 8, 8, 0, 0)] }
    customer_name = models.CharField(max_length=200, null=True, blank=True)
    tckn = models.PositiveBigIntegerField(null=True, blank=True)
    account_opening_date = models.DateTimeField(null=True, blank=True)

    portfolio = models.JSONField(null=True, blank=True)
    portfolio_date = models.DateTimeField(null=True, blank=True)

    transactions = models.JSONField(null=True, blank=True) #strptime(x['tarih'], '%d/%m/%y %H:%M:%S')


    def __str__(self):
        return self.calculator.name
