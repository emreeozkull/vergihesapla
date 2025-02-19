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

    customer_name = models.CharField(max_length=200, null=True, blank=True)
    tckn = models.PositiveBigIntegerField(null=True, blank=True)
    account_opening_date = models.DateTimeField(null=True, blank=True)

    portfolio_date = models.DateTimeField(null=True, blank=True)
    

    def __str__(self):
        return self.calculator.name
    
    def get_portfolio(self):
        return Portfolio.objects.filter(pdf=self)
    
class Transaction(models.Model):
    pdf = models.ForeignKey(CalculatorPDF, on_delete=models.CASCADE)
    date = models.DateTimeField()
    symbol = models.CharField(max_length=200)
    transaction_type = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=28, decimal_places=14)    
    quantity = models.DecimalField(max_digits=28, decimal_places=14)
    transaction_fee = models.DecimalField(max_digits=28, decimal_places=14)
    total_amount = models.DecimalField(max_digits=28, decimal_places=10)
    transaction_status = models.CharField(max_length=200)
    transaction_currency = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.date} - {self.symbol} - {self.transaction_type} - {self.price} - {self.quantity}"

    class Meta:
        ordering = ['-date']

class Portfolio(models.Model):
    pdf = models.ForeignKey(CalculatorPDF, on_delete=models.CASCADE)
    date = models.DateTimeField()
    symbol = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=28, decimal_places=14)
    buy_price = models.DecimalField(max_digits=28, decimal_places=14)
    profit = models.DecimalField(max_digits=28, decimal_places=14)
    

    def __str__(self):
        return f"{self.date} - {self.symbol} - {self.quantity}"
