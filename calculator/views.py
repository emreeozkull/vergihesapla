import json

from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

from datetime import datetime
from decimal import Decimal

from .models import Calculator, CalculatorPDF, Transaction, Portfolio
from .midas import Midas, Stock

def calculator(request):
    return render(request, "calculator/calculator.html")

def create_id_calculator(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            calculator_id = data.get('calculator_id')
            if calculator_id is not None:
                return JsonResponse({'calculator_id': calculator_id})
            else:
                calculator = Calculator.objects.create(name="default_calculator")
                return JsonResponse({'calculator_id': calculator.id})
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid JSON data")
    return HttpResponseBadRequest("Invalid request method")

def upload_pdf(request):
    if request.method == 'POST':
        calculator_id = request.POST.get('calculator_id')
        if calculator_id:
            try:
                calculator = Calculator.objects.get(id=calculator_id)
            except Calculator.DoesNotExist:
                return JsonResponse({'error': 'Calculator not found'}, status=404)
        else:
            return JsonResponse({'error': 'Calculator ID is required'}, status=400)
        
        pdf_file = request.FILES.get('pdf')
        if not pdf_file:
            return JsonResponse({'error': 'PDF file is required'}, status=400)
        
        pdf_object = CalculatorPDF.objects.create(
            calculator=calculator,
            pdf=pdf_file
        )
        
        try:
            check_pdf(pdf_object.id)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
        
        return JsonResponse({
            'message': 'PDF uploaded and processed successfully',
            'calculator_id': calculator.id
        })
    return HttpResponseBadRequest("Invalid request method")

def check_pdf(pdf_id):
    pdf = CalculatorPDF.objects.get(id=pdf_id)
    if not pdf.pdf.name.endswith('.pdf'):
        raise ValueError("Invalid PDF file")
    # Initialize Midas to process the PDF (this extracts info and transactions).
    midas_instance = Midas(pdf)
    print(f"PDF {pdf_id} processed; portfolio_date: {midas_instance.portfolio_date}")

def calculate_tax(profit):
    total_profit_in_tl = Decimal(profit)
    # Calculate tax amount
    if total_profit_in_tl <= 158000:
        tax_amount = total_profit_in_tl * Decimal("0.15")
    elif total_profit_in_tl <= 330000:
        total_profit_in_tl -= Decimal("158000")
        tax_amount = Decimal("23700") + total_profit_in_tl * Decimal("0.20")
    elif total_profit_in_tl <= 800000:
        total_profit_in_tl -= Decimal("330000")
        tax_amount = Decimal("58100") + total_profit_in_tl * Decimal("0.27")
    elif total_profit_in_tl <= 4300000:
        total_profit_in_tl -= Decimal("800000") 
        tax_amount = Decimal("185000") + total_profit_in_tl * Decimal("0.35")
    elif total_profit_in_tl > 4300000:
        total_profit_in_tl -= Decimal("4300000")
        tax_amount = Decimal("1410000") + total_profit_in_tl * Decimal("0.40")
    else: 
        tax_amount = 0
        print("ERROR in tax amount calculation")
    return tax_amount

def get_results(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            calculator_id = data.get('calculator_id')
            cal_context = calculate_results(calculator_id)

            context = {
                'total_profit_loss': f"{cal_context['profit']:.2f}",
                'tax_amount': f"{calculate_tax(cal_context['profit']):.2f}",
                'transaction_count': len(cal_context['transactions']),
                'transactions': cal_context['transactions'],
                'portfolios': [],
                'symbol_profits': cal_context['symbol_profits'],
            }

            
            return render(request, 'vergihesapla/results.html', context)
        except Calculator.DoesNotExist:
            return JsonResponse({'error': 'Calculator not found'}, status=404)
        except Exception as e:
            raise ValueError("val error:", e)
    return render(request, 'vergihesapla/results.html')

def test_transactions(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        calculator_id = data.get('calculator_id')
        calculator = Calculator.objects.get(id=calculator_id)
        pdfs = CalculatorPDF.objects.filter(calculator=calculator).order_by('portfolio_date')
        transactions = Transaction.objects.filter(pdf__in=pdfs).order_by('date')
        return render(request, 'vergihesapla/test_transactions.html', {'transactions': transactions})
    return HttpResponseBadRequest("Invalid request method")

def test_calculation(request, calculator_id):
    context = calculate_results(calculator_id)
    if request.method == 'POST':
        return JsonResponse(context)
    elif request.method == 'GET':   
        return render(request, 'vergihesapla/test_calculation.html', context)
    return HttpResponseBadRequest("Invalid request method")

def calculate_results(calculator_id):
       # Optionally run cleanup_duplicates if needed.
    cleanup_duplicates(calculator_id)
    calculator = Calculator.objects.get(id=calculator_id)
    pdfs = CalculatorPDF.objects.filter(calculator=calculator).order_by('portfolio_date')
    sorted_transactions = Transaction.objects.filter(pdf__in=pdfs).order_by('date')
    symbols = list(set(sorted_transactions.values_list("symbol", flat=True)))
    calculated_stocks = []
    for symbol in symbols:
        sorted_symbol_transactions = Transaction.objects.filter(pdf__in=pdfs, symbol=symbol).order_by('date')
        portfolio_date = sorted_symbol_transactions.first().pdf.portfolio_date
        
        try:
            first_portfolio = Portfolio.objects.get(pdf_id = pdfs.first().id, date = portfolio_date, symbol = symbol)
        except :
            first_portfolio = Portfolio(pdf = pdfs.first(), date = portfolio_date, symbol = symbol, quantity = 0, buy_price = 0, profit = 0)
        stock = Stock(symbol, first_portfolio)

        for transaction in sorted_symbol_transactions:
            cleanup_duplicates(calculator_id)
            if transaction.pdf.portfolio_date != portfolio_date:
                try:
                    portfolio = Portfolio.objects.get(pdf__calculator = calculator , date = portfolio_date, symbol = symbol)
                    with open("portfolio_log.txt", "a") as f:
                        f.write(f"\ntransaction pdf portfolio date: {transaction.pdf.portfolio_date} portfolio month: {portfolio_date.month}\n")
                        f.write(f"portfolio exists, transaction date: {transaction.date}\n")
                except Portfolio.DoesNotExist:
                    with open("portfolio_log.txt", "a") as f:
                        f.write(f"\nportfolio doesn't exist: transaction date: {transaction.date}\n")
                    portfolio = Portfolio(date = portfolio_date, symbol = symbol, quantity = 0, buy_price = 0, profit = 0)
                stock.check_portfolio(portfolio)
                portfolio_date = transaction.pdf.portfolio_date

            if transaction.symbol == symbol:
                if transaction.transaction_type == "Alış":
                    stock.add_transaction(transaction)
                elif transaction.transaction_type == "Satış":
                    stock.calculate_sell_transaction(transaction)
                else:
                    print("Invalid transaction type:", transaction.transaction_type)
                    raise ValueError("Invalid transaction type")     
        
        #check last portfolio with calculation values
        last_pdf_date = pdfs.last().portfolio_date
        try:
            portfolio = Portfolio.objects.get(pdf_id = pdfs.last().id, date = last_pdf_date, symbol = symbol)
        except Portfolio.DoesNotExist:
            portfolio = Portfolio(date = last_pdf_date, symbol = symbol, quantity = 0, buy_price = 0, profit = 0)
            print(f"Portfolio for {symbol} on {last_pdf_date} does not exist")
        if not stock.check_portfolio(portfolio):
            raise ValueError("Portfolio is not corrolated at the end of the calculation")

        calculated_stocks.append(stock)
    context = {
        'profit': sum(stock.profit for stock in calculated_stocks),
        'transactions': [],
        'profits': [stock.profits_sell_transactions for stock in calculated_stocks],
        'symbols': symbols,
        'symbol_profits': [(stock.symbol, round(sum(stock.profits_sell_transactions),2) , round(stock.usd_profit, 2)) for stock in calculated_stocks]
    }
    for stock in calculated_stocks:
        context['transactions'].extend(stock.calculated_sell_transactions)
    return context


def cleanup_duplicates(calculator_id):
    from django.db.models import Count
    from django.db import models

    calculator = Calculator.objects.get(id=calculator_id)
    pdfs = CalculatorPDF.objects.filter(calculator=calculator)
    
    # Find duplicates across all PDFs for this calculator
    duplicates = (Transaction.objects.filter(pdf__in=pdfs)
                 .values('date', 'symbol', 'transaction_type', 'price', 'quantity')
                 .annotate(count=Count('id'))
                 .filter(count__gt=1)
                 .order_by('date'))

    # Print or log the duplicates
    if len(duplicates) > 0:
        print(f"\nFound {len(duplicates)} duplicate transactions:")
        for dup in duplicates:
            print("\nDuplicate group:")
            transactions = Transaction.objects.filter(
                pdf__in=pdfs,
                date=dup['date'],
                symbol=dup['symbol'],
                transaction_type=dup['transaction_type'],
                price=dup['price'],
                quantity=dup['quantity']
            ).order_by('id')
            
            for t in transactions:
                print(f"ID: {t.id}, PDF: {t.pdf.id}, Date: {t.date}, Symbol: {t.symbol}, "
                    f"Type: {t.transaction_type}, Price: {t.price}, Quantity: {t.quantity}")

        # Optionally clean up the duplicates
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
            print(f"\nKept transaction ID {first_transaction.id}, deleted {dup['count']-1} duplicates")
