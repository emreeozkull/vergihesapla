import re
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

        # Find the YATIRIM İŞLEMLERİ section !!! make it more consistent 
        match = re.search(r'YATIRIM İŞLEMLERİ \((.*?)\)(.*?)HESAP İŞLEMLERİ', 
                        self.text, re.DOTALL | re.MULTILINE)
        
        if match:
            transactions_section = match.group(2)
            line_count = sum(1 for line in transactions_section.split('\n') if line.strip())
            print(f"Found transactions section with {line_count} lines")
            
            for line in transactions_section.split('\n'):
                # Skip empty lines, headers, and address lines
                if (line.strip() and 
                    not line.startswith('Tarih') and 
                    not line.startswith('Kayıt') and 
                    not line.startswith('Adres:') and
                    len(line.split()) >= 10):  # Basic validation for transaction lines
                    
                    transaction = self.parse_transaction_line(line)
                    if transaction is not None:
                        transactions.append(transaction)
        else:
            print("!!! transaction lines are not found in this pdf")

        if transactions:
            
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