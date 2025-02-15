import json

from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

from .models import Calculator, CalculatorPDF
from .midasPortfolio import AccountStatement
# Create your views here.

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
    
    #check for endswith pdf

    accountStatement = AccountStatement(pdf.pdf.path)
    account_info = accountStatement.account_info
    pdf.account_opening_date = account_info.get("account_opening_date")[0]
    print("INFO account_opening_date: ", pdf.account_opening_date, type(pdf.account_opening_date))
    pdf.customer_name = account_info.get("customer_name")
    pdf.tckn = int(account_info.get("tckn"))
    print("INFO customer_name: ", pdf.customer_name, pdf.tckn, type(pdf.tckn))

    pdf.portfolio_date = accountStatement.statement_dates[0]
    print("INFO portfolio_date : ", pdf.portfolio_date, type(pdf.portfolio_date))

    pdf.portfolio = accountStatement.portfolio_summary[1]
    print("INFO portfolio: ", pdf.portfolio, type(pdf.portfolio))

    if accountStatement.statement_dates[1] != accountStatement.portfolio_summary[0][0]:
        print("WARNING: Portfolio date does not match statement date.")
        raise ValueError("Portfolio date does not match statement date.")
    
    # check account info with all calculator info 
    # chech account_opening_date  for transactions


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

    pdf.transactions = accountStatement.extract_transactions() # change this to variable in accountStatement

    pdf.save()
    print("pdf checked and saved")

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
            
            for pdf in pdfs:
                print(f"ordered pdf: {pdf.portfolio_date}")
                # check if any pdf is missing 

            # Initialize variables for calculations
            total_profit_loss = 0
            total_transaction_count = 0
            transactions = []
            
            
            calculated_stocks = midas_main(pdfs)
            total_profit_in_tl = 0 
            for stock in calculated_stocks:
                print(f"stock.symbol:{stock.symbol} stock.total_income:{stock.total_income} stock.total_income_usd:{stock.total_income_usd}")
                total_profit_loss += stock.total_income_usd
                total_profit_in_tl += stock.total_income
                total_transaction_count += int(len(stock.all_transactions))
                transactions.append({
                        'symbol': stock.symbol,
                        'type': str(len(stock.all_transactions)),
                        #'quantity': stock.quantity,
                        #'price': stock.price,
                        'total': f"{stock.total_income:.2f}", 
                        'total_usd': f"{stock.total_income_usd:.2f}"
                    })
                
            profit_in_tl = total_profit_in_tl

            # Calculate tax amount
            if total_profit_in_tl <= 158000:
                tax_amount = total_profit_in_tl * 0.15
            elif total_profit_in_tl <= 330000:
                total_profit_in_tl -= 158000
                tax_amount = 23700 + total_profit_in_tl * 0.20
            elif total_profit_in_tl <= 800000:
                total_profit_in_tl -= 330000
                tax_amount = 58100 + total_profit_in_tl * 0.27
            elif total_profit_in_tl <= 4300000:
                total_profit_in_tl -= 800000
                tax_amount = 185000 + total_profit_in_tl * 0.35
            elif total_profit_in_tl > 4300000:
                total_profit_in_tl -= 4300000
                tax_amount = 1410000 + total_profit_in_tl * 0.40
            else: 
                tax_amount = 0
                print("ERROR in tax amount calculation")

            
            context = {
                'total_profit_loss': f"{profit_in_tl:,.2f}",
                'tax_amount': f"{tax_amount:,.2f}",
                'transaction_count': total_transaction_count,
                'transactions': transactions
            }
            
            return render(request, 'vergihesapla/results.html', context)
        except Exception as e:
            print(f"Error: {str(e)}")

            return JsonResponse({'error': str(e)}, status=500)
        
        except Calculator.DoesNotExist:
            return JsonResponse({'error': 'Calculator not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return render(request, 'vergihesapla/results.html')


import json
import datetime
from .stocks import Stock, Portfolio


def print_sold_list(sold_list):
    for i in sold_list:
        print(f"date: {i['date']} adet: {i['adet']} fiyat: {i['fiyat']} income: {i['income']} income_usd: {i['income_usd']} buy_list_end: {i['buy_list_end']}")
        for j in i['buy_list_copy']:
            print(f" date: {j['date']} adet: {j['adet']} fiyat: {j['fiyat']} toplam_tutar: {j['toplam_tutar']}")


def midas_main(pdfs): 
    
    # portfolios
    all_portfolios = {}
    transactions = []
    for pdf in pdfs:
        all_portfolios[pdf.portfolio_date] = pdf.portfolio
        for transaction in pdf.transactions:
            transaction["date"] = datetime.datetime.strptime(transaction["tarih"], "%d/%m/%y %H:%M:%S")
            transactions.append(transaction)
        #DEBUGprint("all transaction date format transformation is finished.")
    

    symbols = {}
    first_transaction_date = transactions[0]["date"]
    first_transaction = transactions[0]
    for i in transactions:
        if first_transaction_date > i["date"]:
            first_transaction_date = i["date"]
            first_transaction = i
            #DEBUGprint(f"first_transaction_date: {first_transaction_date}")
        if i["sembol"] not in symbols:
            symbols[i["sembol"]] = [i]
        else:
            symbols[i["sembol"]].append(i)
    #DEBUGprint(f"symbol appending is finished. symbols: {symbols}\n starting to portfolio...")
    portfolio = Portfolio(first_transaction, all_poftfolios=all_portfolios)
    #DEBUGprint("portfolio is created. portfolio: ",portfolio.portfolio)
    calculated_symbols = []
    all_income = 0
    all_income_usd = 0
    for symbol in symbols:
        print(f"\n{symbol} is starting...")
        stock = Stock(symbols[symbol],portfolio)
        stock.calculate()
        if len(stock.buy_list) > 0:
            print("ERROR: buy list is not empty")
        
        calculated_symbols.append(stock)
        all_income += stock.total_income
        all_income_usd += stock.total_income_usd
        #print("\n*** last calcualted portfolio: ",stock.portfolio.portfolio)
    
    print()
    print(f"all_income: {all_income}")
    print(f"all_income_usd: {all_income_usd}")

    print("midas.py is finished results: ")
    for i in calculated_symbols:
        print(f"{i.symbol} {int(i.total_income)}₺ ${int(i.total_income_usd)}")
    return calculated_symbols