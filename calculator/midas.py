import re
import json
from datetime import datetime, timedelta, timezone

from .models import Calculator, CalculatorPDF, Transaction, Portfolio

from pypdf import PdfReader
from decimal import Decimal

# parse code 

def parse_number(text):
    """Convert string number with comma decimal separator to float"""
    try:
        if isinstance(text, str):
            # Handle numbers with both thousand separators and decimal comma
            # First, check if we have both . and ,
            if '.' in text and ',' in text:
                # Remove the thousand separators (.)
                text = text.replace('.', '')
            # Now replace the decimal comma with a period
            text = text.replace(',', '.')
        return Decimal(text)
    except (ValueError, AttributeError):
        return None
    
class Midas:

    def __init__(self, pdf_object:CalculatorPDF):
        self.pdf_object = pdf_object
        self.path = pdf_object.pdf.path
        self.reader = PdfReader(self.path, strict=True)
        self.text = "\n".join([page.extract_text() for page in self.reader.pages])
        self.lines = [line.strip() for line in self.text.split("\n")]

        if not self.is_valid():
            raise ValueError(
                f"{self.path} is not a valid Midas account statement. "
                "The strings 'Midas Menkul Değerler A.Ş.' or 'HESAP EKSTRESİ' "
                "were not found in the statement."
            )

        self.statement_dates = self.extract_statement_dates()
        self.account_info = self.extract_account_info()
        self.portfolio_date = self.extract_portfolio_summary_get_portfolio_date()
        self.sorted_transactions = self.extract_transactions()

        pdf_object.account_opening_date = self.account_info.get("account_opening_date")[0].astimezone(timezone.utc)
        pdf_object.customer_name = self.account_info.get("customer_name")
        pdf_object.tckn = int(self.account_info.get("tckn"))
        pdf_object.portfolio_date = self.portfolio_date.astimezone(timezone.utc)
        
        pdf_object.save()
        
    def is_valid(self) -> bool:
        if self.reader.metadata.title != "Hesap Ekstresi":
            self.logger.warning(f"reader.metadata.title is not 'Hesap Ekstresi' for {self.path}")
        
        if "Midas Menkul Değerler A.Ş." not in self.text or "HESAP EKSTRESİ" not in self.text:
            return False
        
        return True
    def extract_dates_from_text(self, text: str) -> list[datetime]:
        dates = re.findall(r"\d{2}/\d{2}/\d{2}", text)
        # check if the date is date
        return [datetime.strptime(date, "%d/%m/%y") for date in dates]
    
    def extract_statement_dates(self) -> list[datetime]:
        for line in self.lines:
            if "HESAP EKSTRESİ" in line:
                statement_dates = sorted(self.extract_dates_from_text(line))
                
                if len(statement_dates) != 2:
                    raise ValueError(f"Invalid number of statement dates found in the statement: {len(statement_dates)} dates were found.")
                
                # check if the dates are the first and the last day of the month
                if ((statement_dates[0].day != 1) or 
                    (statement_dates[1].month == (statement_dates[1] + timedelta(days=1)).month)):
                    raise ValueError("The statement dates are not the first and the last day of the month.")

                return statement_dates
            
        raise ValueError("No statement dates were found in the statement.")
    
    def extract_account_info(self) -> dict:
        account_info = {}

        for line in self.lines:
            if "PORTFÖY ÖZETİ" in line and not account_info:
                raise ValueError("Account info not found in the statement.")
            elif "PORTFÖY ÖZETİ" in line and account_info:
                break
            
            if "Müşteri Adı" in line:
                account_info["customer_name"] = line.split(":")[1].strip()
            elif "TCKN" in line:
                # Find exactly 11 digits
                tckn_match = re.search(r'\b\d{11}\b', line)
                if tckn_match:
                    account_info["tckn"] = tckn_match.group()
                else:
                    raise ValueError(f"Could not find valid TCKN in line: {line}")
            elif "Hesap Açılış" in line:
                account_info["account_opening_date"] = self.extract_dates_from_text(line)

        return account_info
    
    def extract_portfolio_summary_get_portfolio_date(self) :

        portfolio_bool = False

        for line in self.lines:
            if "PORTFÖY ÖZETİ" in line:
                portfolio_bool = True

                portfolio_date = self.extract_dates_from_text(line)
                if len(portfolio_date) != 1:
                    raise ValueError("Invalid number of portfolio dates found in the statement: {len(portfolio_date)} dates were found.")
                
            if "YATIRIM İŞLEMLERİ" in line:
                portfolio_bool = False

            if portfolio_bool:
                if "USD" in line:
                    split = line.split()
                    portfolio_symbol = split[0]
                    quantity = parse_number(split[-7])
                    buy_price = parse_number(split[-6])
                    profit = parse_number(split[-4])
                    total_value = parse_number(split[-2])

                    #check total value in here
                    portfolio_object = Portfolio(pdf=self.pdf_object)
                    # Convert datetime to UTC timezone before saving
                    portfolio_object.date = portfolio_date[0].astimezone(timezone.utc)  # Add [0] since portfolio_date is a list
                    portfolio_object.symbol = portfolio_symbol
                    portfolio_object.quantity = quantity
                    portfolio_object.buy_price = buy_price
                    portfolio_object.profit = profit
                    
                    portfolio_object.save()
                    
        return portfolio_date[0]  # Return single datetime object instead of list
    
    def parse_transaction_line(self,line) -> Transaction:
        """Parse a single transaction line into components"""
        parts = line.strip().split()
        if len(parts) < 10:  # Basic validation
            return None
        
        try:
            # Extract date and time
            date = f"{parts[0]} {parts[1]}"
            transaction_date = datetime.strptime(date, '%d/%m/%y %H:%M:%S')
            transaction_date = transaction_date.replace(tzinfo=timezone.utc)

            # Handle cases where the transaction was cancelled or rejected
            if parts[6] in ['İptal', 'Reddedildi','İptal Edildi']:
                return None
                
            # Get the price and amount
            transaction_quantity = parse_number(parts[-4])
            
            # Find the price - it's usually the third-to-last number
            transaction_price = parse_number(parts[-3])
            transaction_fee = parse_number(parts[-2])
            total_price = parse_number(parts[-1])
            
            # Validate all required numbers
            if None in [transaction_quantity, transaction_price, transaction_fee, total_price]:
                return None
            
            transaction_object = Transaction(pdf=self.pdf_object,
                date=transaction_date,
                symbol = parts[4],
                transaction_type = parts[5],
                price = transaction_price,
                quantity = transaction_quantity,
                transaction_fee = transaction_fee,
                total_amount = total_price,
                transaction_status = parts[6],
                transaction_currency = parts[7]
                )
            transaction_object.save()
            return transaction_object

        except (IndexError, ValueError) as e:
            print(f"Error parsing line: {line}")
            print(f"Error details: {str(e)}")
            return None
    
    def extract_transactions(self):
        transactions = []
        print(f"\nProcessing file: {self.path}")

        
        transactions_section = []
        
        transaction_bool = False

        for line in self.lines:
            if "YATIRIM İŞLEMLERİ" in line:
                transaction_bool = True

            if "HESAP İŞLEMLERİ" in line:
                transaction_bool = False

            if transaction_bool and "Tarih" not in line and "Gerçekleşti" in line:
                transactions_section.append(line)

        
        if len(transactions_section) > 0:
            
            line_count = len(transactions_section)

            print(f"Found transactions section with {line_count} lines")
            
            for line in transactions_section:
                # Skip empty lines, headers, and address lines
                if (line.strip() and 
                    not line.startswith('Tarih') and 
                    not line.startswith('Kayıt') and 
                    not line.startswith('Adres:') and
                    len(line.split()) >= 10):  # Basic validation for transaction lines
                    
                    transaction = self.parse_transaction_line(line)
                    if transaction is not None and transaction in transactions:
                        print(f"Transaction {transaction} already exists")
                        with open("duplicate_transactions.txt", "a") as f : 
                            f.write(line + "\n")
                            f.write(f"{transaction} !!! transaction is already in the list: ")
                            for t in transactions:
                                f.write(f"{t}\n")
                        raise ValueError(f"Transaction {transaction} already exists")
                    if transaction is not None and transaction not in transactions:
                        transactions.append(transaction)
        else:
            print("!!! transaction lines are not found in this pdf")
            with open("error_transaction.txt", "a") as f : 
                for line in self.lines:
                    f.write(line + "\n")
                f.write("!!! transaction lines are not found in this pdf")

        if transactions:

            distinct_transactions = Transaction.objects.filter(pdf_id = self.pdf_object.id).distinct()
            if len(distinct_transactions) != len(transactions):
                print(f"WARNING: {len(transactions) - len(distinct_transactions)} transactions were filtered out")
                with open("duplicate_transactions.txt", "a") as f : 
                    f.write(f"WARNING: {len(transactions) - len(distinct_transactions)} transactions were filtered out")
                    for t in distinct_transactions:
                        f.write(f"{t}\n")
            
            sorted_transactions = Transaction.objects.filter(pdf_id = self.pdf_object.id).order_by('date')

            print(f"Returning sorted transactions with length: {len(sorted_transactions)}")
            if len(sorted_transactions) != len(transactions):
                print(f"WARNING: {len(transactions) - len(sorted_transactions)} transactions were filtered out")
            
            with open("transactions.txt", "a") as f:
                f.write(f" portfolio date: {self.portfolio_date}\n")
                for transaction in sorted_transactions:
                    f.write(f"{transaction}\n")
            
            return sorted_transactions
        
        return []

with open("/Users/emreozkul/Desktop/dev-3/scripts-for-midas/hesaplayıcı/converted_ufe.json","r") as read_file :
    ufe_data = json.load(read_file)

with open("/Users/emreozkul/Desktop/dev-3/scripts-for-midas/hesaplayıcı/exchange_rates_2020-2024.json","r") as read_file : # day-month-year
    rates = json.load(read_file)


def get_rate(date: datetime):
    formatted_date = date.strftime("%d-%m-%Y")
    
    # If exact date not found, get closest previous date
    while date:
        date -= timedelta(days=1)
        formatted_date = date.strftime("%d-%m-%Y")
        if formatted_date in rates:
            return Decimal(rates[formatted_date])
    
    raise ValueError(f"No exchange rate found for date {formatted_date}")


def get_ufe(month:int,year:int):
  if month == 1 :
    month = 12 
    year -=1 
  else :
    month -=1 

  for i in ufe_data :
    if i["Year"] == f"{year}" :
      ufe = i[f"{month:02d}"]
      return Decimal(ufe) 
    
def calculate_income(sell_quantity, buy_price, sell_price, buy_date, sell_date):
    sell_ufe = get_ufe(sell_date.month, sell_date.year)
    buy_ufe = get_ufe(buy_date.month, buy_date.year)
    
    # Calculate base amounts
    sell_amount = sell_quantity * sell_price * get_rate(sell_date)
    buy_amount = sell_quantity * buy_price * get_rate(buy_date)
    
    # Apply UFE adjustment if needed
    if (sell_ufe - buy_ufe)/buy_ufe > Decimal(0.1):
        adjusted_buy_amount = buy_amount * (sell_ufe/buy_ufe)
        print(f"ufe income {sell_amount - adjusted_buy_amount}, normal income was {sell_amount - buy_amount}")
        return sell_amount - adjusted_buy_amount
    else:
        print(f"normal income, ufe: {sell_ufe} {buy_ufe} income: {sell_amount - buy_amount}")
        return sell_amount - buy_amount

class Stock:

    invalid_transactions = []
    invalid_sell_transactions = []
    profit = 0

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.transactions = []
        self.buy_transactions = []
        self.calculated_sell_transactions = []
        self.profits_sell_transactions = []
        
        self.portfolios = [] # make it with defaultdict

    def add_transaction(self, transaction: Transaction):
        if transaction.transaction_type == "Alış":
            self.buy_transactions.append(transaction)

    def calculate_sell_transaction(self, transaction: Transaction):
        if transaction.transaction_type == "Satış":
            for buy_transaction in self.buy_transactions:
                if buy_transaction.symbol == transaction.symbol:
                    if buy_transaction.date < transaction.date:

                        if buy_transaction.quantity <= 0:
                            continue
                        
                        transaction_quantity = min(buy_transaction.quantity, transaction.quantity)
                        income = calculate_income(transaction_quantity, buy_transaction.price, transaction.price, buy_transaction.date, transaction.date)
                        self.profit += income
                        self.profits_sell_transactions.append(income)

                        buy_transaction.quantity -= transaction_quantity
                        transaction.quantity -= transaction_quantity

                        if transaction.quantity <= 0:
                            print(f"Transaction calculated: {transaction} with profits: {self.profits_sell_transactions}")
                            self.calculated_sell_transactions.append(transaction)
                            break

            if transaction.quantity > 0:
                self.invalid_sell_transactions.append(transaction)
                print(f"Transaction buy transactions: {self.buy_transactions}")
                raise ValueError(f"Transaction {transaction} has {transaction.quantity} quantity left")




    def add_portfolio(self, portfolio: Portfolio):
        self.portfolios.append(portfolio)


        