import json
import datetime
from .stocks import Stock, Portfolio

def convert_date_format(date_str):
    """Convert date from DD/MM/YY HH:MM:SS to YYYY-MM-DD HH:MM:SS"""
    date_obj = datetime.datetime.strptime(date_str, "%d/%m/%y %H:%M:%S")
    return date_obj

def print_sold_list(sold_list):
    for i in sold_list:
        print(f"date: {i['date']} adet: {i['adet']} fiyat: {i['fiyat']} income: {i['income']} income_usd: {i['income_usd']} buy_list_end: {i['buy_list_end']}")
        for j in i['buy_list_copy']:
            print(f" date: {j['date']} adet: {j['adet']} fiyat: {j['fiyat']} toplam_tutar: {j['toplam_tutar']}")



def main(midas_transactions_path:str):  #midas_transactions.json
    
    #DEBUGprint("starting in main midas.py\nwith midas_transactions_path: ", midas_transactions_path)
    # portfolios
    all_portfolios = {}
    with open(midas_transactions_path,"r") as read_file:
        data = json.load(read_file)
        #DEBUGprint("reading portfolios...")
        portfolios_json = data["portfolios"]
        #DEBUGprint(f"portfolios: {portfolios_json}\nreading transactions...")
        test_transactions = data["yatirim_islemleri_2024"]
        #DEBUGprint(f"transactions: {test_transactions}")
        for transaction in test_transactions:
            transaction["date"] = convert_date_format(transaction["tarih"])
            #DEBUGprint("all transaction date format transformation is finished.")
        #convert all keys in portfolio to datetime object
        for date in portfolios_json:
            date_obj = datetime.datetime.strptime(date, "%d/%m/%y")
            all_portfolios[date_obj] = portfolios_json[date]
            #DEBUGprint("all portfolio transformation is finished.\n all_portfolios: ", all_portfolios)

    symbols = {}
    transactions = test_transactions
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
        print("\n",stock.symbol," stock.sold_list end",print_sold_list(stock.sold_list))
        if len(stock.buy_list) > 0:
            print("\n",stock.symbol," stock.buy_list end",stock.buy_list) # it should be empty 
        calculated_symbols.append(stock)
        all_income += stock.total_income
        all_income_usd += stock.total_income_usd
        print("\n*** last calcualted portfolio: ",stock.portfolio.portfolio)
    
    print()
    print(f"all_income: {all_income}")
    print(f"all_income_usd: {all_income_usd}")

    print("midas.py is finished results: ")
    for i in calculated_symbols:
        print(f"{i.symbol} {int(i.total_income)}₺ ${int(i.total_income_usd)}")
    return calculated_symbols