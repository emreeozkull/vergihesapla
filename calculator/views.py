from django.shortcuts import render

# Create your views here.
import json
import datetime
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

from .models import Calculator, CalculatorPDF



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
    if not pdf.pdf.name.endswith('.pdf'):
        return JsonResponse({'error': 'Invalid PDF file'}, status=400)
    pdf.save()
    print("pdf checked and saved")


def calculate_results(request):
    if request.method == 'POST':
        try:
  
            context = {
                'total_profit_loss': "0.00",
                'tax_amount': "0.00",
                'transaction_count': "0",
                'transactions': [],
            }
            
            return render(request, 'vergihesapla/results.html', context)
        
        except Calculator.DoesNotExist:
            return JsonResponse({'error': 'Calculator not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return render(request, 'vergihesapla/results.html')


def midas_main(pdfs): 
    pass