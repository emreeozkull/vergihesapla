import logging
import re

from datetime import datetime, timedelta
from pypdf import PdfReader


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
            logger.warning(f"reader.metadata.title is not 'Hesap Ekstresi' for {self.path}")
        
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


                
                
