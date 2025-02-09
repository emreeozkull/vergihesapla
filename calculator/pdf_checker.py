from pypdf import PdfReader

import os 

def extract_investment_transactions(pdf_path):

    reader = PdfReader(pdf_path)

    print(len(reader.pages))
    text = ""
    for page in reader.pages:
        text += page.extract_text()
        text += "\n\n"

    print(text)

    with open(f'{pdf_path.rstrip(".pdf")}.txt', 'w') as f:
        f.write(text)


def extract_all_transactions(pdf_directory):

    # Process each PDF file in the directory
    for filename in os.listdir(pdf_directory):
        if filename.endswith('.pdf'):
            pdf_path = os.path.join(pdf_directory, filename)
            print(f"\nProcessing file: {filename}")
            
            extract_investment_transactions(pdf_path)


