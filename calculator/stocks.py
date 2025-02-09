import json
import datetime

with open("/Users/emreozkul/Desktop/dev-3/scripts-for-midas/hesaplayıcı/converted_ufe.json","r") as read_file :
    ufe_data = json.load(read_file)

with open("/Users/emreozkul/Desktop/dev-3/scripts-for-midas/hesaplayıcı/exchange_rates_2020-2024.json","r") as read_file : # day-month-year
    rates = json.load(read_file)


def get_rate(date:datetime.datetime):
    date -= datetime.timedelta(days=1)
    day = date.day
    month = date.month
    year = date.year

    while True :
        try: 
            rate = rates[date.strftime("%d-%m-%Y")] 
            break
        except :
            date -= datetime.timedelta(days=1)
    return rate


def get_ufe(month:int,year:int):
  if month == 1 :
    month = 12 
    year -=1 
  else :
    month -=1 

  for i in ufe_data :
    if i["Year"] == f"{year}" :
      ufe = i[f"{month:02d}"]
      return float(ufe) 
    
def calculate_income(quantity, buy_price, sell_price, buy_date, sell_date):
    sell_ufe = get_ufe(sell_date.month, sell_date.year)
    buy_ufe = get_ufe(buy_date.month, buy_date.year)
    
    # Calculate base amounts
    sell_amount = quantity * sell_price * get_rate(sell_date)
    buy_amount = quantity * buy_price * get_rate(buy_date)
    
    # Apply UFE adjustment if needed
    if (sell_ufe - buy_ufe)/buy_ufe > 0.1:
        adjusted_buy_amount = buy_amount * (sell_ufe/buy_ufe)
        print(f"ufe income {sell_amount - adjusted_buy_amount}, normal income was {sell_amount - buy_amount}")
        return sell_amount - adjusted_buy_amount
    else:
        print(f"normal income, ufe: {sell_ufe} {buy_ufe} income: {sell_amount - buy_amount}")
        return sell_amount - buy_amount


class Portfolio :
    
    #all_portfolio = {} # {date: {symbol: {quantity: int, price: float} , symbol: {quantity: int, price: float}}, ... }

    portfolio = {} # {symbol: {quantity: int, price: float, date: datetime} ,symbol: {quantity: int, price: float, date: datetime}, ... }

    def __init__(self, first_transaction, all_poftfolios) :
        # first transaction date is not first portfolio !!! 
        #self.first_transaction_date = datetime.datetime.strptime(f"01/{first_transaction['date'].month}/{first_transaction['date'].year}", "%d/%m/%Y")
        self.first_transaction_date = min(all_poftfolios.keys())
        self.all_portfolios = all_poftfolios
        self.last_transaction_date = max(all_poftfolios.keys()) # change it to real last transaction date
        self.check_first_month()
        for k, v in all_poftfolios[self.first_transaction_date].items():
            self.portfolio[k] = v

    def check_first_month(self):
        pass
    
    def add_to_portfolio(self, transaction):
        date = transaction["date"]
        symbol = transaction["sembol"]
        if transaction["islem_tipi"] == "Alış":
            if symbol in self.portfolio:
                self.portfolio[symbol]["quantity"] += transaction["adet"]
            else:
                self.portfolio[symbol] = {"quantity": transaction["adet"], "price": transaction["fiyat"], "date": date}
        elif transaction["islem_tipi"] == "Satış":
            print("!!! worning sell in portfolio not wanted")
        else: 
            print(f"!!! Worning transaction type {transaction['islem_tipi']} in {date.strftime('%Y-%m-%d')} with {transaction['adet']} transactions ")
    
    def sell_from_portfolio(self, symbol, quantity):
        if symbol in self.portfolio:
            self.portfolio[symbol]["quantity"] -= quantity
        else:
            print(f"!!! Worning symbol {symbol} is not in portfolio but try to sell !!!")
    
    def check_portfolio(self, symbol):
        if self.portfolio[symbol]["quantity"] != self.all_portfolios[self.last_transaction_date][symbol]["quantity"]:
            print("ERROR: portfolio is not equal to last portfolio")
            print(f"last transaction date: {self.last_transaction_date}")
            print(f"last transaction portfolio: {self.all_portfolios[self.last_transaction_date]}")
            print(f"current portfolio: {self.portfolio}")
            return False
        else: 
            print("portfolio is equal to last portfolio")
            return True

class Stock :
   
   first_buy_date = ""

   def __init__(self, stock_symbol_data, portfolio:Portfolio) :
      self.all_transactions = stock_symbol_data
      self.symbol = stock_symbol_data[0]["sembol"]
      self.total_income = 0 
      self.total_income_usd = 0
      self.buy_list = []
      self.sold_list = []
      self.sell_not_found = []
      self.portfolio = portfolio

   def calculate(self):
      self.buy_list = []
      self.sold_list = []
      self.total_income = 0
      self.total_income_usd = 0
      
      sorted_transactions = sorted(self.all_transactions, key=lambda x: x["date"])
      

      for transaction in sorted_transactions:
          if transaction["islem_tipi"] == "Alış":
              self.buy_list.append(transaction)
              self.portfolio.add_to_portfolio(transaction) # buy 
          elif transaction["islem_tipi"] == "Satış":
              if (transaction["date"].year) == 2024:
                self.calculate_transaction(transaction) #sell so portfolio calculation in buy
          else:
              print("unknown transaction", transaction)
      
      print(f"all transactions finished in symbol {self.symbol} starting check portfolio...")
      try:
        self.portfolio.check_portfolio(self.symbol) # prints and returns 
      except Exception as e:
        print("!"*25)
        print("ERROR: problem in check portfolio exception", e)


   def calculate_transaction(self, transaction):
        transaction_income = 0
        transaction_usd_income = 0
        transaction_quantity = transaction["adet"]
        buy_list_copy = self.buy_list.copy()
        
        for buy in buy_list_copy:
            if buy["adet"] <= 0:
                continue
                
            if buy["date"] > transaction["date"]: # check for same day transaction
                continue
            
            process_quantity = min(transaction_quantity, buy["adet"])
            
            portion_income = calculate_income(process_quantity,buy["fiyat"],transaction["fiyat"],buy["date"],transaction["date"])
            
            portion_usd_income = process_quantity * (transaction["fiyat"] - buy["fiyat"])
            
            transaction_income += portion_income
            transaction_usd_income += portion_usd_income
            
            buy["adet"] -= process_quantity
            self.portfolio.sell_from_portfolio(buy["sembol"], process_quantity)
            transaction_quantity -= process_quantity
            
            if buy["adet"] <= 0:
                #DEBUGprint(f"\n\nbuy is removing from buy_list... buy:{buy}, buy_list: {self.buy_list}")
                self.buy_list.remove(buy)
                #DEBUGprint(f"\nbuy removed from buy_list... buy_list: {self.buy_list}")
            
            if transaction_quantity <= 0:
                break

        if transaction_quantity > 0:
            self.sell_not_found.append(transaction)
            print("*"*100)
            print(f"\n\n{transaction} not found in buy_list")
            print("*"*100,f"\nbuy_list: {self.buy_list}")
            print("*"*100,"\nsold list" , self.print_sold_list() ,"\n","*"*100)


        if transaction_quantity < transaction["adet"]:
            transaction_copy = transaction.copy()
            transaction_copy["income"] = transaction_income
            transaction_copy["income_usd"] = transaction_usd_income
            transaction_copy["buy_list_copy"] = buy_list_copy
            transaction_copy["buy_list_end"] = self.buy_list
            self.sold_list.append(transaction_copy) # just sell transactions add buy transactions as well

            self.total_income += transaction_income
            self.total_income_usd += transaction_usd_income
    
   def print_sold_list(self):
    for i in self.sold_list : 
        print(f"date: {i['date']} adet: {i['adet']} fiyat: {i['fiyat']} income: {i['income']} income_usd: {i['income_usd']} buy_list_end: {i['buy_list_end']}")
        for j in i['buy_list_copy']:
            print(f" date: {j['date']} adet: {j['adet']} fiyat: {j['fiyat']} toplam_tutar: {j['toplam_tutar']}")

