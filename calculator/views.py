from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseBadRequest
from .models import Calculator, CalculatorPDF
from .pdf_checker import extract_investment_transactions
import json
from django.views.decorators.csrf import csrf_exempt
from .midas_text_to_json import main as text_to_json
from .midas import main as midas_main
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
    extract_investment_transactions(pdf.pdf.path)

    accountStatement = AccountStatement(pdf.pdf.path)
    account_info = accountStatement.account_info
    pdf.account_opening_date = account_info.get("account_opening_date")[0]
    print("INFO account_opening_date: ", pdf.account_opening_date, type(pdf.account_opening_date))
    pdf.customer_name = account_info.get("customer_name")
    pdf.tckn = account_info.get("tckn")
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
        print("ERROR: TCKN does not match.")
        raise ValueError("TCKN does not match.")

    if pdf.calculator.customer_name == None:
        pdf.calculator.customer_name = pdf.customer_name
        pdf.calculator.save()
    elif pdf.customer_name != pdf.calculator.customer_name:
        print("ERROR: Customer name does not match.")
        raise ValueError("Customer name does not match.")

    if pdf.calculator.account_opening_date == None:
        pdf.calculator.account_opening_date = pdf.account_opening_date
        pdf.calculator.save()
    elif pdf.account_opening_date != pdf.calculator.account_opening_date:
        print("ERROR: Account opening date does not match.")
        raise ValueError("Account opening date does not match.")

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
            pdfs = CalculatorPDF.objects.filter(calculator=calculator)
            
            # Initialize variables for calculations
            total_profit_loss = 0
            total_transaction_count = 0
            transactions = []

            for pdf in pdfs:
                text_path = pdf.pdf.path.rstrip(".pdf") + ".txt"
                #DEBUGprint(f"text path: {text_path}")
                base_dir = text_path.rsplit("/", 1)[0]
                text_to_json(base_dir)
                #transactions = json.load(open(f'{base_dir}/midas_transactions_2024.json'))
                #DEBUGprint(f"transactions: {transactions}")
            #DEBUGprint("starting to calculate with midas_main ...\n base_dir: ", base_dir)
            calculated_stocks = midas_main(f'{base_dir}/midas_transactions_2024.json')
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
                'total_profit_loss': f"{total_profit_in_tl:,.2f}",
                'tax_amount': f"{tax_amount:,.2f}",
                'transaction_count': total_transaction_count,
                'transactions': transactions
            }
            
            return render(request, 'vergihesapla/results.html', context)
        except Exception as e:
            print(f"Error: {str(e)}")

            return render(request, 'vergihesapla/results.html', context)
        
        except Calculator.DoesNotExist:
            return JsonResponse({'error': 'Calculator not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return render(request, 'vergihesapla/results.html')

