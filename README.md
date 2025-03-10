# Vergi Hesapla

A web application that helps Turkish investors calculate their taxes for investments made in US stock markets (NYSE, NASDAQ) through the Midas platform.

## Features

- 📊 Quick Tax Calculation: Upload your Midas account statements and get instant tax calculations for your 2024 US stock market investments
- 📄 PDF Statement Processing: Automatically analyze Midas account statements
- 📱 Responsive Design: Works seamlessly on both desktop and mobile devices
- 📋 Detailed Reports: Get comprehensive PDF reports of your transactions and earnings
- 🔒 Secure Processing: Your files are processed securely and deleted after calculation

## Tech Stack

- Django 4.0+
- Python 3.x
- HTML5/CSS3
- JavaScript
- SQLite3

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/vergihesapla.git
cd vergihesapla
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Apply database migrations:
```bash
python manage.py migrate
```

5. Run the development server:
```bash
python manage.py runserver
```

The application will be available at `http://localhost:8000`

## Project Structure

```
vergihesapla/
├── calculator/           # Calculator app for tax calculations
├── static/              # Static files (CSS, JS, images)
├── templates/           # HTML templates
├── vergihesapla/        # Main project directory
└── manage.py           # Django management script
```

## Usage

1. Visit the homepage
2. Click on "Hesapla" to start a new calculation
3. Upload your Midas account statements (PDF format)
4. Wait for the automatic analysis
5. View your tax calculation results
6. Download detailed PDF report

## Security Note

This tool is for reference purposes only and does not constitute accounting services. We recommend consulting with a financial advisor before filing your tax returns.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

The tax calculations provided by this tool are for reference purposes only. Users should verify all calculations with a qualified financial advisor before filing tax returns. 