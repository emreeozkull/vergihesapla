import logging
import re

from datetime import datetime, timedelta
from pypdf import PdfReader

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
        return float(text)
    except (ValueError, AttributeError):
        return None

def parse_transaction_line(line):
    """Parse a single transaction line into components"""
    parts = line.strip().split()
    if len(parts) < 10:  # Basic validation
        return None
    
    try:
        # Extract date and time
        date = f"{parts[0]} {parts[1]}"
        
        # Handle cases where the transaction was cancelled or rejected
        if parts[6] in ['İptal', 'Reddedildi']:
            return None
            
        # Get the price and amount
        adet = parse_number(parts[10])
        
        # Find the price - it's usually the third-to-last number
        fiyat = parse_number(parts[-3])
        islem_ucreti = parse_number(parts[-2])
        toplam_tutar = parse_number(parts[-1])
        
        # Validate all required numbers
        if None in [adet, fiyat, islem_ucreti, toplam_tutar]:
            return None
            
        # Extract other fields
        transaction = {
            "tarih": date,
            "islem_turu": f"{parts[2]} {parts[3]}",
            "sembol": parts[4],
            "islem_tipi": parts[5],
            "durum": parts[6],
            "para_birimi": parts[7],
            "adet": adet,
            "fiyat": fiyat,
            "islem_ucreti": islem_ucreti,
            "toplam_tutar": toplam_tutar
        }
        return transaction
    except (IndexError, ValueError) as e:
        print(f"Error parsing line: {line}")
        print(f"Error details: {str(e)}")
        return None
    
class AccountStatement:
    logger = logging.getLogger(__name__)
    def __init__(self, path):
        self.path = path
        self.reader = PdfReader(path, strict=True)
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
        self.portfolio_summary = self.extract_portfolio_summary()
        
    def is_valid(self) -> bool:
        if self.reader.metadata.title != "Hesap Ekstresi":
            self.logger.warning(f"reader.metadata.title is not 'Hesap Ekstresi' for {self.path}")
        
        if "Midas Menkul Değerler A.Ş." not in self.text or "HESAP EKSTRESİ" not in self.text:
            return False
        
        return True
    
    # dd/mm/yy format, years >= 69 are interpreted as 1969-1999,
    # years < 69 are interpreted as 2000-2068
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
    
    def extract_portfolio_summary(self) -> dict:
        portfolio_summary = []
        portfolio_dict = {}
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
                    symbol = split[0]
                    quantity = float(split[-7].replace(",", "."))
                    buy_price = float(split[-6].replace(",", "."))
                    profit = float(split[-4].replace(",", "."))
                    total_value = float(split[-2].replace(",", "."))

                    portfolio_summary.append({
                        "symbol": symbol,
                        "quantity": quantity,
                        "buy_price": buy_price,
                        "profit": profit,
                        "total_value": total_value
                    })

                    portfolio_dict[symbol] = {
                        "symbol": symbol,
                        "quantity": quantity,
                        "buy_price": buy_price,
                        "profit": profit,
                        "total_value": total_value
                    }
                    
        return portfolio_date, portfolio_dict
    
    def extract_transactions(self):
        transactions = []
    

        print(f"\nProcessing file: {self.path}")
        

        # Find the YATIRIM İŞLEMLERİ section
        match = re.search(r'YATIRIM İŞLEMLERİ \((.*?)\)(.*?)HESAP İŞLEMLERİ', 
                        self.text, re.DOTALL | re.MULTILINE)
        
        if match:
            transactions_section = match.group(2)
            line_count = sum(1 for line in transactions_section.split('\n') if line.strip())
            print(f"Found transactions section with {line_count} lines")
            
            for line in transactions_section.split('\n'):
                if line.strip() and not line.startswith('Tarih') and not line.startswith('Kayıt'):
                    transaction = parse_transaction_line(line)
                    if transaction is not None:
                        transactions.append(transaction)
        
        sorted_transactions = sorted(transactions, key=lambda x: datetime.strptime(x['tarih'], '%d/%m/%y %H:%M:%S') if x['tarih'] else x['tarih'])
        print("returning sorted transactions with length: ", len(sorted_transactions))
        if len(sorted_transactions) != len(transactions):
            print(f"WARNING: {len(transactions) - len(sorted_transactions)} transactions were not sorted")
            
        return sorted_transactions


                
                
