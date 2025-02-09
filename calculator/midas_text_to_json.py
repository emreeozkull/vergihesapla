import os
import json
import re
from datetime import datetime

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

def parse_portfolio_line(line):
    """Parse a single portfolio line into components"""
    parts = line.strip().split()
    if len(parts) < 8:  # Basic validation
        print(f"Warning: Incomplete portfolio line: {line}")
        return None
    
    try:
        # Extract symbol (first part before the dash)
        symbol = parts[0]
        
        # Find the numeric values
        # Format: symbol name adet maliyet USD kar_zarar USD toplam_deger USD
        numbers = []
        for part in reversed(parts):
            if part != 'USD':
                num = parse_number(part)
                if num is not None:
                    numbers.append(num)
                if len(numbers) == 4:
                    break
        
        if len(numbers) < 4:
            print(f"Warning: Not enough numeric values in line: {line}")
            return None
            
        # Numbers are in reverse order
        toplam_deger, kar_zarar, hisse_maliyet, adet = numbers
            
        portfolio_item = {
            "sembol": symbol,
            "quantity": adet,
            "price": hisse_maliyet,
            "kar_zarar": kar_zarar,
            "toplam_deger": toplam_deger
        }
        return portfolio_item
    except (IndexError, ValueError) as e:
        print(f"Error parsing portfolio line: {line}")
        print(f"Error details: {str(e)}")
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

def process_midas_statement(file_path):
    """Process a single Midas statement file"""
    transactions = []
    portfolio = {}
    portfolio_date = None
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            print(f"\nProcessing file: {file_path}")
            
            # Debug: Print file content around PORTFÖY ÖZETİ
            portfolio_index = content.find('PORTFÖY ÖZETİ')
            if portfolio_index != -1:
                print("Found PORTFÖY ÖZETİ at position:", portfolio_index)
                context = content[max(0, portfolio_index-20):min(len(content), portfolio_index+200)]
                print("Context around PORTFÖY ÖZETİ:")
                print(context)
                
                # Try different regex patterns
                patterns = [
                    r'PORTFÖY ÖZETİ\s*\(\s*\)(\d{2}/\d{2}/\d{2})(.*?)(?=YATIRIM İŞLEMLERİ)',
                    r'PORTFÖY ÖZETİ\s*\(\s*\)(\d{2}/\d{2}/\d{2})',
                    r'PORTFÖY ÖZETİ.*?\((.*?)\)(.*?)(?=YATIRIM İŞLEMLERİ)',
                    r'PORTFÖY ÖZETİ.*?\((.*?)\)(.*?)(?=\*Kar)'
                ]
                
                for i, pattern in enumerate(patterns):
                    print(f"\nTrying pattern {i+1}: {pattern}")
                    portfolio_match = re.search(pattern, content, re.DOTALL | re.MULTILINE)
                    if portfolio_match:
                        print(f"Matched pattern {i+1}")
                        portfolio_date = portfolio_match.group(1).strip()
                        if len(portfolio_match.groups()) > 1:
                            portfolio_section = portfolio_match.group(2)
                        else:
                            # If we only matched the date, get the section manually
                            start = content.find('Sermaya Piyasası Aracı')
                            end = content.find('YATIRIM İŞLEMLERİ', start)
                            if start != -1 and end != -1:
                                portfolio_section = content[start:end]
                            else:
                                print("Couldn't find portfolio section boundaries")
                                continue
                        
                        print(f"Found portfolio section for date: {portfolio_date}")
                        print("Portfolio section content:")
                        print(portfolio_section[:200])  # Print first 200 chars
                        
                        # Process each portfolio line
                        for line in portfolio_section.split('\n'):
                            if line.strip() and not line.startswith('Sermaya') and not line.startswith('*'):
                                print(f"Processing line: {line}")
                                portfolio_item = parse_portfolio_line(line)
                                if portfolio_item is not None:
                                    symbol = portfolio_item["sembol"]
                                    portfolio[symbol] = portfolio_item
                                    print(f"Added portfolio item: {portfolio_item}")
                        
                        print(f"Found {len(portfolio)} portfolio items")
                        break
                else:
                    print("No pattern matched the portfolio section")
            else:
                print("No PORTFÖY ÖZETİ found in file")
            
            # Find the YATIRIM İŞLEMLERİ section
            match = re.search(r'YATIRIM İŞLEMLERİ \((.*?)\)(.*?)HESAP İŞLEMLERİ', 
                            content, re.DOTALL | re.MULTILINE)
            
            if match:
                transactions_section = match.group(2)
                line_count = sum(1 for line in transactions_section.split('\n') if line.strip())
                print(f"Found transactions section with {line_count} lines")
                
                for line in transactions_section.split('\n'):
                    if line.strip() and not line.startswith('Tarih') and not line.startswith('Kayıt'):
                        transaction = parse_transaction_line(line)
                        if transaction is not None:
                            transactions.append(transaction)
                            
    except Exception as e:
        print(f"Error processing file {file_path}: {str(e)}")
    
    return transactions, portfolio, portfolio_date

def get_all_midas_transactions(base_dir):
    """Get all transactions from all statement files"""
    all_transactions = []
    portfolios = {}  # Dictionary to store portfolios by date
    
    # Check if directory exists
    if not os.path.exists(base_dir):
        print(f"Directory not found: {base_dir}")
        return all_transactions, portfolios
    
    # Walk through the directory structure
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith('.txt'):
                file_path = os.path.join(root, file)
                transactions, portfolio, portfolio_date = process_midas_statement(file_path)
                if transactions:
                    print(f"Found {len(transactions)} transactions in {file}")
                if portfolio and portfolio_date:
                    portfolios[portfolio_date] = portfolio
                all_transactions.extend(transactions)
    
    # Sort transactions by date
    if all_transactions:
        all_transactions.sort(key=lambda x: datetime.strptime(x['tarih'], '%d/%m/%y %H:%M:%S'))
    
    return all_transactions, portfolios

def main(base_dir:str):

    # process all directories
    #base_dirs = ["/Users/emreozkul/Desktop/dev-3/scripts-for-midas/hesaplama-yeni/texts/test","/Users/emreozkul/Desktop/dev-3/scripts-for-midas/hesaplama-yeni/texts/2024"]
    
    all_transactions = []
    all_portfolios = {}
    
    print(f"\nProcessing directory: {base_dir}")
    if not os.path.exists(base_dir):
        print(f"Directory not found: {base_dir}")
        return
    else:
        print("Files in directory:")
        for f in os.listdir(base_dir):
            print(f"  {f}")
            
        transactions, portfolios = get_all_midas_transactions(base_dir)
        all_transactions.extend(transactions)
        all_portfolios.update(portfolios)
    
    # Create the final JSON structure
    output = {
        "yatirim_islemleri_2024": all_transactions,
        "portfolios": all_portfolios
    }
    
    # Write to JSON file
    with open(f'{base_dir}/midas_transactions_2024.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\nSummary:")
    print(f"Successfully processed {len(all_transactions)} total transactions")
    print(f"Successfully processed {len(all_portfolios)} portfolio snapshots")
    print("JSON file has been created: midas_transactions_2024.json")

if __name__ == "__main__":
    main() 