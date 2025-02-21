import re
import json
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.db import transaction, OperationalError, IntegrityError
from .models import Calculator, CalculatorPDF, Transaction, Portfolio
from pypdf import PdfReader

def parse_number(text):
    """Convert a string number with comma as decimal separator to Decimal."""
    try:
        if isinstance(text, str):
            # Remove thousand separators if both '.' and ',' exist.
            if '.' in text and ',' in text:
                text = text.replace('.', '')
            text = text.replace(',', '.')
        return Decimal(text)
    except (ValueError, AttributeError):
        return None

def atomic_get_or_create(model, defaults, **kwargs):
    """
    Attempts to get or create an object inside an atomic transaction.
    Retries a few times if an OperationalError occurs (e.g. "database is locked").
    """
    retries = 5
    delay = 0.5  # initial delay in seconds
    while retries > 0:
        try:
            with transaction.atomic():
                obj, created = model.objects.get_or_create(defaults=defaults, **kwargs)
            return obj, created
        except OperationalError as e:
            if "database is locked" in str(e):
                retries -= 1
                time.sleep(delay)
                delay *= 2  # exponential backoff
            else:
                raise
    raise OperationalError("Operation failed after multiple retries due to a locked database.")

class Midas:
    def __init__(self, pdf_object: CalculatorPDF):
        self.pdf_object = pdf_object
        self.path = pdf_object.pdf.path
        self.reader = PdfReader(self.path, strict=True)
        self.text = "\n".join([page.extract_text() for page in self.reader.pages])
        self.lines = [line.strip() for line in self.text.split("\n")]

        if not self.is_valid():
            raise ValueError(
                f"{self.path} is not a valid Midas account statement. "
                "The strings 'Midas Menkul Değerler A.Ş.' or 'HESAP EKSTRESİ' were not found in the statement."
            )

        self.statement_dates = self.extract_statement_dates()
        self.account_info = self.extract_account_info()
        self.portfolio_date = self.extract_portfolio_summary_get_portfolio_date()
        self.sorted_transactions = self.extract_transactions()

        # Save extracted info to the PDF object.
        self.pdf_object.account_opening_date = self.account_info.get("account_opening_date")[0].astimezone(timezone.utc)
        self.pdf_object.customer_name = self.account_info.get("customer_name")
        self.pdf_object.tckn = int(self.account_info.get("tckn"))
        self.pdf_object.portfolio_date = self.portfolio_date.astimezone(timezone.utc)
        self.pdf_object.save()
    
    def is_valid(self) -> bool:
        # Optional: log a warning if metadata.title isn’t as expected.
        if self.reader.metadata.title != "Hesap Ekstresi":
            print(f"Warning: metadata.title is not 'Hesap Ekstresi' for {self.path}")
        return "Midas Menkul Değerler A.Ş." in self.text and "HESAP EKSTRESİ" in self.text

    def extract_dates_from_text(self, text: str) -> list:
        dates = re.findall(r"\d{2}/\d{2}/\d{2}", text)
        return [datetime.strptime(date, "%d/%m/%y") for date in dates]
    
    def extract_statement_dates(self) -> list:
        for line in self.lines:
            if "HESAP EKSTRESİ" in line:
                statement_dates = sorted(self.extract_dates_from_text(line))
                if len(statement_dates) != 2:
                    raise ValueError(f"Invalid number of statement dates found: {len(statement_dates)}")
                # Check if dates represent the first and last day of the month.
                if (statement_dates[0].day != 1 or 
                    statement_dates[1].month == (statement_dates[1] + timedelta(days=1)).month):
                    raise ValueError("The statement dates are not the first and last day of the month.")
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
                tckn_match = re.search(r'\b\d{11}\b', line)
                if tckn_match:
                    account_info["tckn"] = tckn_match.group()
                else:
                    raise ValueError(f"Could not find valid TCKN in line: {line}")
            elif "Hesap Açılış" in line:
                account_info["account_opening_date"] = self.extract_dates_from_text(line)
        return account_info
    
    def extract_portfolio_summary_get_portfolio_date(self):
        portfolio_bool = False
        portfolio_date = None
        for line in self.lines:
            if "PORTFÖY ÖZETİ" in line:
                portfolio_bool = True
                portfolio_date_list = self.extract_dates_from_text(line)
                if len(portfolio_date_list) != 1:
                    raise ValueError(f"Invalid number of portfolio dates found: {len(portfolio_date_list)}")
                portfolio_date = portfolio_date_list[0]
            if "YATIRIM İŞLEMLERİ" in line:
                portfolio_bool = False
            if portfolio_bool and "USD" in line:
                split = line.split()
                portfolio_symbol = split[0]
                quantity = parse_number(split[-7])
                buy_price = parse_number(split[-6])
                profit = parse_number(split[-4])
                portfolio_object = Portfolio(pdf=self.pdf_object)
                portfolio_object.date = portfolio_date.astimezone(timezone.utc)
                portfolio_object.symbol = portfolio_symbol
                portfolio_object.quantity = quantity
                portfolio_object.buy_price = buy_price
                portfolio_object.profit = profit
                portfolio_object.save()
        if portfolio_date is None:
            raise ValueError("No portfolio date found in the statement.")
        return portfolio_date
    
    def parse_transaction_line(self, line) -> Transaction:
        """Return an unsaved Transaction instance from a transaction line."""
        parts = line.strip().split()
        if len(parts) < 10:
            return None
        try:
            date_str = f"{parts[0]} {parts[1]}"
            transaction_date = datetime.strptime(date_str, '%d/%m/%y %H:%M:%S')
            transaction_date = transaction_date.replace(tzinfo=timezone.utc)
            if parts[6] in ['İptal', 'Reddedildi', 'İptal Edildi']:
                return None
            transaction_quantity = parse_number(parts[-4])
            transaction_price = parse_number(parts[-3])
            transaction_fee = parse_number(parts[-2])
            total_price = parse_number(parts[-1])
            if None in [transaction_quantity, transaction_price, transaction_fee, total_price]:
                return None
            # Create and return a Transaction instance (do not save yet)
            transaction_object = Transaction(
                pdf=self.pdf_object,
                date=transaction_date,
                symbol=parts[4],
                transaction_type=parts[5],
                price=transaction_price,
                quantity=transaction_quantity,
                transaction_fee=transaction_fee,
                total_amount=total_price,
                transaction_status=parts[6],
                transaction_currency=parts[7]
            )
            return transaction_object
        except (IndexError, ValueError) as e:
            print(f"Error parsing line: {line}\nDetails: {str(e)}")
            return None

    def extract_transactions(self):
        # Avoid reprocessing if transactions already exist for this PDF.
        if Transaction.objects.filter(pdf_id=self.pdf_object.id).exists():
            print("Transactions for this PDF already exist, skipping extraction.")
            return Transaction.objects.filter(pdf_id=self.pdf_object.id).order_by('date')
        
        transactions = []
        print(f"Processing file: {self.path}")
        transactions_section = []
        transaction_bool = False

        # Extract lines belonging to the transaction section.
        for line in self.lines:
            if "YATIRIM İŞLEMLERİ" in line:
                transaction_bool = True
            if "HESAP İŞLEMLERİ" in line:
                transaction_bool = False
            if transaction_bool and "Tarih" not in line and "Gerçekleşti" in line:
                transactions_section.append(line)

        if transactions_section:
            print(f"Found transactions section with {len(transactions_section)} lines")
            seen_transactions = set()
            for line in transactions_section:
                if (line.strip() and not line.startswith('Tarih') and 
                    not line.startswith('Kayıt') and not line.startswith('Adres:') and 
                    len(line.split()) >= 10):
                    transaction_obj = self.parse_transaction_line(line)
                    if transaction_obj is None:
                        continue
                    # Define a signature for duplicate checking.
                    signature = (
                        transaction_obj.date,
                        transaction_obj.symbol,
                        transaction_obj.transaction_type,
                        transaction_obj.price,
                        transaction_obj.quantity
                    )
                    if signature in seen_transactions:
                        print(f"Skipping duplicate transaction in current run: {transaction_obj}")
                        continue
                    seen_transactions.add(signature)
                    
                    try:
                        # Use our atomic_get_or_create helper to safely insert the transaction.
                        obj, created = atomic_get_or_create(
                            Transaction,
                            pdf=self.pdf_object,
                            date=transaction_obj.date,
                            symbol=transaction_obj.symbol,
                            transaction_type=transaction_obj.transaction_type,
                            price=transaction_obj.price,
                            quantity=transaction_obj.quantity,
                            defaults={
                                'transaction_fee': transaction_obj.transaction_fee,
                                'total_amount': transaction_obj.total_amount,
                                'transaction_status': transaction_obj.transaction_status,
                                'transaction_currency': transaction_obj.transaction_currency,
                            }
                        )
                        if created:
                            transactions.append(obj)
                        else:
                            print(f"Duplicate found via get_or_create: {obj}")
                    except IntegrityError:
                        print("IntegrityError: Duplicate transaction detected.")
                        continue
        else:
            print("No transaction lines found in PDF.")
            with open("error_transaction.txt", "a") as f:
                for line in self.lines:
                    f.write(line + "\n")
                f.write("No transaction lines found in this PDF.\n")
        
        sorted_transactions = Transaction.objects.filter(pdf_id=self.pdf_object.id).order_by('date')
        print(f"Returning sorted transactions with count: {sorted_transactions.count()}")
        with open("transactions.txt", "a") as f:
            f.write(f"Portfolio date: {self.portfolio_date}\n")
            for t in sorted_transactions:
                f.write(f"{t}\n")
        return sorted_transactions

# --- UFE and Exchange Rate Functions ---

with open("/Users/emreozkul/Desktop/dev-3/scripts-for-midas/hesaplayıcı/converted_ufe.json", "r") as read_file:
    ufe_data = json.load(read_file)

with open("/Users/emreozkul/Desktop/dev-3/scripts-for-midas/hesaplayıcı/exchange_rates_2020-2024.json", "r") as read_file:
    rates = json.load(read_file)

def get_rate(date: datetime):
    formatted_date = date.strftime("%d-%m-%Y")
    while date:
        date -= timedelta(days=1)
        formatted_date = date.strftime("%d-%m-%Y")
        if formatted_date in rates:
            return Decimal(str(rates[formatted_date]))
    raise ValueError(f"No exchange rate found for date {formatted_date}")

def get_ufe(month: int, year: int):
    if month == 1:
        month = 12
        year -= 1
    else:
        month -= 1
    for i in ufe_data:
        if i["Year"] == f"{year}":
            return Decimal(str(i[f"{month:02d}"]))

def calculate_income(sell_quantity, buy_price, sell_price, buy_date, sell_date):
    sell_ufe = get_ufe(sell_date.month, sell_date.year)
    buy_ufe = get_ufe(buy_date.month, buy_date.year)
    sell_amount = sell_quantity * sell_price * get_rate(sell_date)
    buy_amount = sell_quantity * buy_price * get_rate(buy_date)
    if (sell_ufe - buy_ufe) / buy_ufe > Decimal(0.1):
        adjusted_buy_amount = buy_amount * (sell_ufe / buy_ufe)
        print(f"UFE income: {sell_amount - adjusted_buy_amount}, normal income: {sell_amount - buy_amount}")
        return sell_amount - adjusted_buy_amount
    else:
        print(f"Normal income: {sell_amount - buy_amount} (UFE: {sell_ufe} vs {buy_ufe})")
        return sell_amount - buy_amount

class Stock:
    invalid_transactions = []
    invalid_sell_transactions = []
    debug_buy_transactions = []
    debug_sell_transactions = []
    profit = 0

    def __init__(self, symbol: str, portfolio: Portfolio):
        self.symbol = symbol
        self.transactions = []
        self.buy_transactions = []
        self.calculated_sell_transactions = []
        self.profits_sell_transactions = []
        self.portfolio = Portfolio(pdf = portfolio.pdf, date = portfolio.date, symbol = portfolio.symbol, quantity = Decimal(0), buy_price = portfolio.buy_price, profit = portfolio.profit)

    def add_transaction(self, transaction: Transaction):
        if transaction.symbol == self.symbol and transaction.transaction_type == "Alış":
            copy_transaction = {
                "date": transaction.date.strftime("%d/%m/%y"),
                "quantity": str(transaction.quantity)
            }
            self.debug_buy_transactions.append(copy_transaction)
            self.buy_transactions.append(transaction)
            self.portfolio.quantity += transaction.quantity # for portfolio tracking

    def calculate_sell_transaction(self, transaction: Transaction):
        if transaction.symbol == self.symbol and transaction.transaction_type == "Satış":
            copy_transaction = {
                "date": transaction.date.strftime("%d/%m/%y"),
                "quantity": str(transaction.quantity)
            }
            self.debug_sell_transactions.append(copy_transaction)
            for buy_transaction in self.buy_transactions:
                if buy_transaction.symbol == transaction.symbol and buy_transaction.date < transaction.date:
                    if buy_transaction.quantity <= 0:
                        continue
                    transaction_quantity = min(buy_transaction.quantity, transaction.quantity)
                    income = calculate_income(
                        transaction_quantity,
                        buy_transaction.price,
                        transaction.price,
                        buy_transaction.date,
                        transaction.date
                    )
                    if transaction.date.year == 2024:
                        self.profit += income
                    self.profits_sell_transactions.append(income)
                    buy_transaction.quantity -= transaction_quantity
                    self.portfolio.quantity -= transaction_quantity # for portfolio tracking
                    transaction.quantity -= transaction_quantity
                    if transaction.quantity <= 0:
                        self.calculated_sell_transactions.append(transaction)
                        break
            if transaction.quantity > 0:
                self.invalid_sell_transactions.append(transaction)
                raise ValueError(f"Transaction {transaction} has {transaction.quantity} quantity left")

    def add_portfolio(self, portfolio: Portfolio):
        self.portfolios.append(portfolio)

    def check_portfolio(self, portfolio: Portfolio):
        if portfolio.symbol != self.symbol:
            raise ValueError(f"Portfolio symbol {portfolio.symbol} does not match stock symbol {self.symbol}")
        else:
            if self.portfolio.quantity == portfolio.quantity:
                with open("portfolio_log.txt", "a") as f:
                    f.write(f"check portfolio date: {portfolio.date}\n")
                    f.write(f"success: {self.symbol} - calculated portfolio:{self.portfolio.quantity} vs {portfolio.quantity}\n")
                return True
            else:
                with open("portfolio_log.txt", "a") as f:
                    f.write(f"check portfolio date: {portfolio.date} \nerror:")
                    f.write(f"{self.symbol} - calculated portfolio:{self.portfolio.quantity} vs {portfolio.quantity}\n")
                    f.write(f"buy transactions: {str(self.debug_buy_transactions)}\n")
                    f.write(f"sell transactions: {str(self.debug_sell_transactions)}\n")
                    if self.symbol == "AMZN":
                        f.write(f"buy transactions: {str(self.buy_transactions)}\n")
                        f.write(f"calculated sell transactions: {str(self.calculated_sell_transactions)}\n")
                        f.write(f"profits sell transactions: {str(self.profits_sell_transactions)}\n")
                #raise ValueError("portfolio is not corrolated")
                return False 

