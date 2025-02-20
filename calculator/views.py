from django.shortcuts import render

# Create your views here.
import json
import datetime
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

from .models import Calculator, CalculatorPDF, Transaction, Portfolio
from .midas import Midas, Stock



def calculator(request):
    return render(request,"calculator/calculator.html")

def create_id_calculator(request):
    if request.method == 'POST':
        try:
            # Parse JSON data from request body
            data = json.loads(request.body)
            calculator_id = data.get('calculator_id')
            print("came to server calculator_id: ", calculator_id)
            if calculator_id is not None:    
                print("calculator_id exists: ", calculator_id)
                return JsonResponse({'calculator_id': calculator_id})
            else:
                print("creating new calculator, calculator_id does not exist", calculator_id)
                # Create a new calculator
                calculator = Calculator.objects.create(name="default_calculator")
                return JsonResponse({'calculator_id': calculator.id})
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid JSON data")
    else:
        return HttpResponseBadRequest("Invalid request method")
    
def upload_pdf(request):
    if request.method == 'POST':
        # Get calculator_id from request or create new calculator
        calculator_id = request.POST.get('calculator_id')
        
        if calculator_id:
            calculator = Calculator.objects.get(id=calculator_id)
        else:
            print("!!!no calcualtor id in request to upload_pdf, calculator_id: ", calculator_id)
            return JsonResponse({'error': 'Calculator ID is required'}, status=400)
        
        pdf_object = CalculatorPDF.objects.create(
            calculator=calculator,
            pdf=request.FILES.get('pdf')
        )

        check_pdf(pdf_object.id)
        return JsonResponse({
            'message': 'PDF uploaded successfully',
            'calculator_id': calculator.id
        })
    else:
        return HttpResponseBadRequest("Invalid request method")

def check_pdf(pdf_id):
    pdf = CalculatorPDF.objects.get(id=pdf_id)
    calculator = pdf.calculator
    #check for endswith pdf
    if not pdf.pdf.name.endswith('.pdf'):
        return JsonResponse({'error': 'Invalid PDF file'}, status=400)
    
    midas_pdf = Midas(pdf)
    #check for valid pdf

    if pdf.calculator.tckn == None:
        pdf.calculator.tckn = pdf.tckn
        pdf.calculator.save()
    elif pdf.tckn != pdf.calculator.tckn:
        print(f"ERROR: TCKN does not match. pdf.tckn: {pdf.tckn}, pdf.calculator.tckn: {pdf.calculator.tckn} and types are: {type(pdf.tckn)}, {type(pdf.calculator.tckn)}")
        raise ValueError("TCKN does not match.")

    if pdf.calculator.customer_name == None:
        pdf.calculator.customer_name = pdf.customer_name
        pdf.calculator.save()
    elif pdf.customer_name != pdf.calculator.customer_name:
        print(f"ERROR: Customer name does not match. pdf.customer_name: {pdf.customer_name}, pdf.calculator.customer_name: {pdf.calculator.customer_name} and types are: {type(pdf.customer_name)}, {type(pdf.calculator.customer_name)}")
        raise ValueError("Customer name does not match.")

    if pdf.calculator.account_opening_date == None:
        pdf.calculator.account_opening_date = pdf.account_opening_date
        pdf.calculator.save()
    elif pdf.account_opening_date.astimezone() != pdf.calculator.account_opening_date:
        print(f"ERROR: Account opening date does not match. pdf.date : {pdf.account_opening_date}, pdf.calculator.account_opening_date: {pdf.calculator.account_opening_date}, types are: {type(pdf.account_opening_date)}, {type(pdf.calculator.account_opening_date)}")
        raise ValueError("Account opening date does not match.")

    
    pdf.save()
    print(f"date: {pdf.portfolio_date} pdf checked and saved")


def calculate_results(request):
    if request.method == 'POST':
        try:
             # Parse the JSON data from request body
            data = json.loads(request.body)
            calculator_id = data.get('calculator_id')
            
            # Get the calculator instance
            calculator = Calculator.objects.get(id=calculator_id)
            
            # Get all PDFs associated with this calculator
            pdfs = CalculatorPDF.objects.filter(calculator=calculator).order_by('portfolio_date')

            transactions = Transaction.objects.filter(pdf__in=pdfs).order_by('date')
            
            context = {
                'total_profit_loss': "0.00",
                'tax_amount': "0.00",
                'transaction_count': "0",
                'transactions': transactions,
                'portfolios': [],
            }
            
            return render(request, 'vergihesapla/results.html', context)
        
        except Calculator.DoesNotExist:
            return JsonResponse({'error': 'Calculator not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return render(request, 'vergihesapla/results.html')


def midas_main(pdfs): 
    pass

def test_transactions(request):
    
    if request.method == 'POST':

        data = json.loads(request.body)
        calculator_id = data.get('calculator_id')
        
        # Get the calculator instance
        calculator = Calculator.objects.get(id=calculator_id)
        
        # Get all PDFs associated with this calculator
        pdfs = CalculatorPDF.objects.filter(calculator=calculator).order_by('portfolio_date')

        transactions = Transaction.objects.filter(pdf__in=pdfs).order_by('date')
        

        return render(request, 'vergihesapla/test_transactions.html', {'transactions': transactions})
    
def test_calculation(request, calculator_id):

    if request.method == 'GET': # change this to post
        #data = json.loads(request.body)
        #calculator_id = data.get('calculator_id')
        print("calculator_id: ", calculator_id)

        cleanup_duplicates(calculator_id)


        # Get the calculator instance
        calculator = Calculator.objects.get(id=calculator_id)
        
        # Get all PDFs associated with this calculator
        pdfs = CalculatorPDF.objects.filter(calculator=calculator).order_by('portfolio_date')

        sorted_transactions = Transaction.objects.filter(pdf__in=pdfs).order_by('date')

        symbols = list(set(sorted_transactions.values_list("symbol", flat=True)))

        calculated_stocks = []

        for symbol in symbols:
            print("symbol: ", symbol)
            stock = Stock(symbol)

            for transaction in sorted_transactions: 
                if transaction.symbol == symbol:
                    if transaction.transaction_type == "Alış":
                        stock.add_transaction(transaction)
                    elif transaction.transaction_type == "Satış":
                        stock.calculate_sell_transaction(transaction)
                    else:
                        print("transaction type is not valid: ", transaction.transaction_type)
                        stock.invalid_transactions.append(transaction)
            print("in views, calculation is finished for stock: ", stock.symbol, "with profit: ", stock.profit)
            calculated_stocks.append(stock)


        show_transactions = []
        context = {
            'profit': 0,
            'transactions': [],
            'profits': [],
            'symbols': [],
            'symbol_profits': []
        }

        for stock in calculated_stocks:
            context['transactions'].extend(stock.calculated_sell_transactions)
            context['profit'] += stock.profit
            context['profits'].append(stock.profits_sell_transactions)
            
            context['symbol_profits'].append((stock.symbol, stock.profit))
        return render(request, 'vergihesapla/test_calculation.html', context)
    return HttpResponseBadRequest("Invalid request method")

def cleanup_duplicates(calculator_id):
    from django.db import models
    
    calculator = Calculator.objects.get(id=calculator_id)
    pdfs = CalculatorPDF.objects.filter(calculator=calculator)
    
    # Find duplicates
    duplicates = (Transaction.objects.filter(pdf__in=pdfs)
                 .values('date', 'symbol', 'transaction_type', 'price', 'quantity')
                 .annotate(count=models.Count('id'))
                 .filter(count__gt=1))
    
    # For each set of duplicates, keep only the first one
    for dup in duplicates:
        transactions = Transaction.objects.filter(
            pdf__in=pdfs,
            date=dup['date'],
            symbol=dup['symbol'],
            transaction_type=dup['transaction_type'],
            price=dup['price'],
            quantity=dup['quantity']
        ).order_by('id')
        
        # Keep the first one, delete the rest
        first_transaction = transactions.first()
        transactions.exclude(id=first_transaction.id).delete()
