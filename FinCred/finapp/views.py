from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
#from django.http import JsonResponse
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from .models import User, Transaction, Detail, Budget, Stock, StockPortfolio, EMI, SavingsAccount, categories
from rest_framework.exceptions import ValidationError
from django.views.generic import DetailView, ListView, CreateView, UpdateView, DeleteView
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import  AuthenticationForm
from django.contrib import messages
from .forms import CustomUserCreationForm, TransactionForm, BudgetForm, SavingsAccountForm,EMICreateForm, StockPortfolioForm
import requests
from django.urls import reverse
from django.db.models import Sum
import json
from django.core.serializers.json import DjangoJSONEncoder
from datetime import datetime
import yfinance as yf


# Create your views here.
def landing(request):
    return render(request, 'landing.html')

def index(request):
    print('hello')
    return render(request, 'index.html')


#def dashboard(request):
    #return render(request, 'dashboardnew.html')


def chart(request):
    return render(request, 'chart.html')


def signup_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Signup successful! Welcome, you're now logged in.")
            return redirect('/dashboardnew/')  # Redirect to the user's profile
        else:
            messages.error(request, "Signup failed. Please fix the errors.")
    else:
        form = CustomUserCreationForm()  # Use CustomUserCreationForm here
    return render(request, 'signup.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            print(f"User {user.username} logged in successfully.")  # Debugging user login
            print(f"User authenticated after login: {request.user.is_authenticated}")  # Check if user is authenticated
            messages.success(request, "Logged in successfully!")
            
            # Test with hardcoded redirect to check if it's a URL issue
            return redirect('/dashboardnew/')  # Hardcoded redirect to test
            
        else:
            print("Form invalid:", form.errors)  # Debugging form errors
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
        print("Rendering login page.")  # Debugging when rendering login page

    return render(request, 'login.html', {'form': form})




def logout_view(request):
    """
    Handles user logout.
    """
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login')  # Redirect to login page after logout

# ------------------- USER PROFILE VIEWS -------------------

@login_required
def dashboard(request):
    """
    Display the user's profile with summary of transactions, budgets, etc.
    """
    user = request.user
    transactions = Transaction.objects.filter(user=user).order_by('-time')[:5]  # Latest 5 transactions
    budgets = Budget.objects.filter(user=user)
    stock_portfolio = StockPortfolio.objects.filter(user=user)
    emi_loans = EMI.objects.filter(user=user)
    savings_account = SavingsAccount.objects.filter(user=user).first()
    detail = Detail.objects.filter(user=user).order_by('-date_created').first()
    

    context = {
        'user': user,
        'transactions': transactions,
        'budgets': budgets,
        'stock_portfolio': stock_portfolio,
        'emi_loans': emi_loans,
        'savings_account': savings_account,
        'detail': detail,
    }
    return render(request, 'dashboardnew.html', context)


# ------------------- TRANSACTION VIEWS -------------------

@method_decorator(login_required, name='dispatch')
class TransactionListView(ListView):
    model = Transaction
    template_name = 'charts.html'
    paginate_by = 10

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user).order_by('-time')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['transactions'] = Transaction.objects.filter(user=self.request.user).order_by('-time')
        return context


@method_decorator(login_required, name='dispatch')
class TransactionDetailView(DetailView):
    model = Transaction
    template_name = 'newtransaction.html'

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)


@method_decorator(login_required, name='dispatch')
@method_decorator(csrf_protect, name='dispatch')
class TransactionCreateView(CreateView):
    model = Transaction
    #fields = ['details', 'amount', 'type', 'credit', 'description', 'tags']
    form_class = TransactionForm
    template_name = 'newtransaction.html'
    success_url = reverse_lazy('transaction_create')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user  # Pass the user to the form
        return kwargs

    def form_valid(self, form):
        # Set the user for the transaction instance
        form.instance.user = self.request.user        
        # Ensure a savings account is set if available
        savings_account = SavingsAccount.objects.filter(user=self.request.user).first()
        if savings_account:
            form.instance.savings_account = savings_account
        
        # Now validate the form and save the instance
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
@method_decorator(csrf_protect, name='dispatch')
class TransactionDeleteView(DeleteView):
    model = Transaction
    form_class = BudgetForm
    template_name = 'transactiondelete.html'
    success_url = reverse_lazy('chart')

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)
    

@login_required
def transaction_overview(request):
    user = request.user
    transactions = Transaction.objects.filter(user=user).order_by('-time')

    # Handle date filtering
    selected_date = request.GET.get('date', None)
    if selected_date:
        transactions = transactions.filter(time__date=selected_date)

    # Get current month
    current_month = datetime.now().month

    # Calculate monthly earnings (assumed type 7 is 'income')
    monthly_earnings = transactions.filter(type=7, time__month=current_month).aggregate(total=Sum('amount'))['total'] or 0

    # Calculate monthly expenses (excluding type 7 for 'income')
    monthly_expenses = transactions.filter(time__month=current_month).exclude(type=7).aggregate(total=Sum('amount'))['total'] or 0

    # Get the balance from the user's savings account
    savings_account = SavingsAccount.objects.filter(user=user).first()
    balance = savings_account.balance if savings_account else 0.0

    # Get total expenditure from details
    details = Detail.objects.filter(user=user).first()
    total_expenditure = details.total_expenditure if details else 0.0

    # Prepare data for charts (daily expenses, etc.)
    daily_expenses = transactions.values('time__date').annotate(total=Sum('amount')).order_by('time__date')
    expense_distribution = transactions.values('type').annotate(total=Sum('amount'))

    # Prepare data for charts
    dates = [entry['time__date'].strftime('%Y-%m-%d') for entry in daily_expenses]
    expenses = [entry['total'] for entry in daily_expenses]

    # Get category names from the categories tuple defined in your models
    categories_dict = dict(categories)
    category_names = [categories_dict.get(entry['type'], "Unknown") for entry in expense_distribution]
    category_totals = [entry['total'] for entry in expense_distribution]

    # Pass everything to context
    context = {
        'transactions': transactions,
        'selected_date': selected_date if selected_date else '',
        'monthly_earnings': monthly_earnings,
        'monthly_expenses': monthly_expenses,
        'balance': balance,  # Added balance
        'total_expenditure': total_expenditure,  # Added total expenditure
        'dates': json.dumps(dates, cls=DjangoJSONEncoder),
        'expenses': json.dumps(expenses, cls=DjangoJSONEncoder),
        'categories': json.dumps(category_names, cls=DjangoJSONEncoder),
        'category_totals': json.dumps(category_totals, cls=DjangoJSONEncoder),
    }

    return render(request, 'chart.html', context)





# ------------------- BUDGET VIEWS -------------------

@method_decorator(login_required, name='dispatch')
class BudgetListView(ListView):
    model = Budget
    template_name = 'newbudget.html'
    paginate_by = 10

    def get_queryset(self):
        print(f"Current user: {self.request.user}")
        return Budget.objects.filter(user=self.request.user).order_by('-date_created')
    


@method_decorator(login_required, name='dispatch')
class BudgetDetailView(DetailView):
    model = Budget
    template_name = 'budget_detail.html'

    def get_queryset(self):
        return Budget.objects.filter(user=self.request.user)

@method_decorator(login_required, name='dispatch')
class BudgetCreateView(CreateView):
    model = Budget
    form_class = BudgetForm  # Use the custom form class
    template_name = 'newbudget.html'
    success_url = reverse_lazy('budget_create')  # Redirect to budget list after creation

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user  # Pass the user to the form
        return kwargs

    def get_context_data(self, **kwargs):
        # Adding additional context if necessary
        context = super().get_context_data(**kwargs)
        context['budgets'] = Budget.objects.filter(user=self.request.user).order_by('-date_created')
        return context
    
@method_decorator(login_required, name='dispatch')
class BudgetDeleteView(DeleteView):
    model = Budget
    template_name = 'budget_delete.html'
    success_url = reverse_lazy('budget_create')  # Redirect to budget list after deletion

    def get_queryset(self):
        # Ensure the user can only delete their own budgets
        return Budget.objects.filter(user=self.request.user)




# ------------------- STOCK PORTFOLIO VIEWS -------------------

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView
from .models import StockPortfolio, Stock
from .forms import StockPortfolioForm

# ------------------- CLASS-BASED VIEWS -------------------
NIFTY_50_SYMBOLS = [
    "RELIANCE.NS", "HDFCBANK.NS", "TCS.NS", "INFY.NS", "ICICIBANK.NS", "SBIN.NS",
    # Add the remaining Nifty 50 stock symbols
]

@method_decorator(login_required, name='dispatch')
class StockPortfolioListView(ListView):
    model = StockPortfolio
    template_name = 'stock_list.html'

    def get_queryset(self):
        # Fetch user's stock portfolio
        return StockPortfolio.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Fetch Nifty 50 stock data from Yahoo Finance
        stocks_data = []
        for symbol in NIFTY_50_SYMBOLS:
            stock = yf.Ticker(symbol)
            stock_info = stock.info
            stocks_data.append({
                'symbol': symbol,
                'name': stock_info.get('longName', 'N/A'),
                'price': stock_info.get('regularMarketPrice', 'N/A'),
                'market_cap': stock_info.get('marketCap', 'N/A')
            })
        
        context['nifty_50_stocks'] = stocks_data
        return context


@method_decorator(login_required, name='dispatch')
class StockPortfolioDetailView(DetailView):
    model = StockPortfolio
    template_name = 'stock_detail.html'

    def get_queryset(self):
        return StockPortfolio.objects.filter(user=self.request.user)

# ------------------- FUNCTION-BASED VIEWS -------------------

@login_required
def stock_portfolio(request):
    user = request.user
    portfolio = StockPortfolio.objects.filter(user=user)
    total_value = sum(stock.current_value for stock in portfolio)

    context = {
        'portfolio': portfolio,
        'total_value': total_value,
    }
    return render(request, 'stock_portfolio.html', context)

@login_required
def stock_detail(request, stock_id):
    stock = get_object_or_404(Stock, id=stock_id)
    future_price = stock.predict_price()  # Assuming you have a method for price prediction

    return render(request, 'stock_detail.html', {
        'stock': stock,
        'future_price': future_price
    })


import yfinance as yf

@login_required
def add_to_portfolio(request, stock_id=None):
    stock = None
    current_price = None

    if stock_id:
        stock = get_object_or_404(Stock, ticker=stock_id)
        # Fetch real-time stock price from yfinance
        stock_data = yf.Ticker(stock.ticker)
        current_price = stock_data.history(period="1d")['Close'][0]

    if request.method == 'POST':
        form = StockPortfolioForm(request.POST)
        if form.is_valid():
            stock_portfolio = form.save(commit=False)
            stock_portfolio.user = request.user
            stock_portfolio.save()
            return redirect('stock_portfolio')
    else:
        form = StockPortfolioForm(initial={'purchase_price': current_price})

    context = {
        'form': form,
        'stocks': Stock.objects.all(),
        'selected_stock': stock,
        'current_price': current_price,
    }
    return render(request, 'add_to_portfolio.html', context)


@login_required
def predict_stock_price(request, stock_id):
    stock = get_object_or_404(Stock, id=stock_id)
    future_price = stock.predict_price()

    return render(request, 'stock_detail.html', {
        'stock': stock,
        'future_price': future_price
    })

import yfinance as yf
from django.http import JsonResponse
from datetime import datetime, timedelta

@login_required
def get_visualizations(request):
    today = datetime.now().date()
    one_month_ago = today - timedelta(days=30)
    
    stock_ticker = request.GET.get('stock_id', 'RELIANCE.NS')  # Default ticker for testing
    stock_name = stock_ticker.split('.')[0] if stock_ticker != 'all' else "All Stocks"
    
    if stock_ticker == 'all':
        return JsonResponse({'message': "Fetching data for all stocks not supported in this demo."})
    
    # Fetch historical data from yfinance
    stock_data = yf.Ticker(stock_ticker).history(start=one_month_ago, end=today)
    
    # Extract key fields for visualization
    dates = stock_data.index.strftime('%Y-%m-%d').tolist()
    open_prices = stock_data['Open'].tolist()
    high_prices = stock_data['High'].tolist()
    low_prices = stock_data['Low'].tolist()
    close_prices = stock_data['Close'].tolist()
    daily_returns = stock_data['Close'].pct_change().fillna(0).tolist()
    cumulative_returns = (1 + stock_data['Close'].pct_change().fillna(0)).cumprod().tolist()
    
    # Summary metrics
    latest_close = close_prices[-1] if close_prices else 0
    previous_close = close_prices[-2] if len(close_prices) > 1 else latest_close
    price_change = latest_close - previous_close
    price_change_percent = (price_change / previous_close) * 100 if previous_close else 0
    
    # Prepare data for response
    candlestick_data = {
        'x': dates,
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices
    }
    
    returns_data = {
        'dates': dates,
        'daily_returns': daily_returns,
        'cumulative_returns': cumulative_returns
    }
    
    return JsonResponse({
        'candlestick': candlestick_data,
        'returns': returns_data,
        'summary': {
            'latest_close': latest_close,
            'price_change': price_change,
            'price_change_percent': price_change_percent
        }
    })

# ------------------- SAVINGS ACCOUNT VIEWS -------------------

@method_decorator(login_required, name='dispatch')
class SavingsAccountDetailView(DetailView):
    model = SavingsAccount
    template_name = 'savings_account.html'

    def get_queryset(self):
        return SavingsAccount.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        savings_account = context['savingsaccount']  # This is set by the DetailView
        context['savings_account'] = savings_account
        return context


@login_required
def savings_deposit(request, account_id):
    """
    Deposit funds into a savings account.
    """
    savings_account = get_object_or_404(SavingsAccount, id=account_id, user=request.user)
    if request.method == 'POST':
        amount = float(request.POST.get('amount', 0))
        if amount > 0:
            savings_account.add_deposit(amount)
            messages.success(request, f"${amount} deposited successfully.")
        else:
            messages.error(request, "Invalid amount.")
        return redirect('savings_account_deposit', account_id=account_id)
    return render(request, 'savings_account.html', {'savings_account': savings_account})


@login_required
def savings_withdraw(request, account_id):
    """
    Withdraw funds from a savings account.
    """
    savings_account = get_object_or_404(SavingsAccount, id=account_id, user=request.user)
    if request.method == 'POST':
        amount = float(request.POST.get('amount', 0))
        try:
            savings_account.withdraw(amount)
            messages.success(request, f"${amount} withdrawn successfully.")
        except Exception as e:
            messages.error(request, str(e))
        return redirect('savings_account_deposit', account_id=account_id)
    return render(request, 'savings_account.html', {'savings_account': savings_account})


@login_required
def create_savings_account(request):
    """
    Allow users to create a new savings account.
    """
    if request.method == 'POST':
        form = SavingsAccountForm(request.POST)
        if form.is_valid():
            # Save the form without committing to set the user
            savings_account = form.save(commit=False)
            savings_account.user = request.user
            savings_account.save()
            messages.success(request, "Savings account created successfully!")
            return redirect('dashboardnew')  # Redirect to the dashboard or any other relevant page
    else:
        form = SavingsAccountForm()

    return render(request, 'createsavingsaccount.html', {'form': form})


# ------------------- Detail VIEWS -------------------

# Detail List View
@method_decorator(login_required, name='dispatch')
class DetailListView(ListView):
    model = Detail
    template_name = 'detail_list.html'
    paginate_by = 10

    def get_queryset(self):
        return Detail.objects.filter(user=self.request.user).order_by('-date_created')


# Detail View (Display monthly financial statement)
@method_decorator(login_required, name='dispatch')
class DetailDetailView(DetailView):
    model = Detail
    template_name = 'detail_detail.html'

    def get_queryset(self):
        return Detail.objects.filter(user=self.request.user)


# Create a New Monthly Detail
@method_decorator(login_required, name='dispatch')
class DetailCreateView(CreateView):
    model = Detail
    fields = [
        'income', 'savings', 'total_expenditure', 'housing',
        'food', 'healthcare', 'transportation', 'recreation', 'others', 'stock'
    ]
    template_name = 'detail_form.html'
    success_url = reverse_lazy('detail_list')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


# Update Monthly Detail
@method_decorator(login_required, name='dispatch')
class DetailUpdateView(UpdateView):
    model = Detail
    fields = [
        'income', 'savings', 'total_expenditure', 'housing',
        'food', 'healthcare', 'transportation', 'recreation', 'others', 'stock'
    ]
    template_name = 'dashboardnew.html'
    success_url = reverse_lazy('dashboardnew')

    def get_queryset(self):
        return Detail.objects.filter(user=self.request.user)

# ------------------- EMI VIEWS -------------------

# EMI List View
@method_decorator(login_required, name='dispatch')
class EMIListView(ListView):
    model = EMI
    template_name = 'emi_detail.html'
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['emi_loans'] = self.get_queryset()  # Add this line
        return context

    def get_queryset(self):
        return EMI.objects.filter(user=self.request.user)


# EMI Detail View
@method_decorator(login_required, name='dispatch')
class EMIDetailView(DetailView):
    model = EMI
    template_name = 'emi_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['emi_loans'] = self.get_queryset()  # Add this line
        return context

    def get_queryset(self):
        return EMI.objects.filter(user=self.request.user)


# EMI Create View
@method_decorator(login_required, name='dispatch')
class EMICreateView(CreateView):
    model = EMI
    form_class = EMICreateForm 
    template_name = 'createemi.html'
    success_url = reverse_lazy('emi_detail')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user  # Pass the user to the form
        return kwargs

    def get_context_data(self, **kwargs):
        # Adding additional context if necessary
        context = super().get_context_data(**kwargs)
        context['emi_loans'] = EMI.objects.filter(user=self.request.user).order_by('-start_date')
        return context
    
    def get_success_url(self):
        # Redirect to the detail page of the newly created EMI
        return reverse('emi_detail', kwargs={'pk': self.object.pk})

@login_required
def emi_make_payment(request, emi_id):
    emi = get_object_or_404(EMI, id=emi_id, user=request.user)
    if request.method == 'POST':
        try:
            amount = float(request.POST.get('amount', 0))
            emi.make_payment(amount)
            messages.success(
                request,
                f"Successfully paid ${amount}. Outstanding balance is now ${emi.outstanding_balance}. "
                f"Savings account balance: ${emi.linked_savings_account.balance if emi.linked_savings_account else 'N/A'}."
            )
        except ValidationError as e:
            messages.error(request, str(e))
        except ValueError:
            messages.error(request, "Invalid payment amount.")
    return redirect('emi_detail', pk=emi_id)

    

@login_required
def emi_detail(request, pk):
    emi = get_object_or_404(EMI, id=pk, user=request.user)
    return render(request, 'emi_detail.html', {'emi': emi})


def savings_list_view(request):
    savings = SavingsAccount.objects.filter(user=request.user)
    return render(request, 'list.html', {'object_list': savings, 'list_what': 'Savings'})

def deposit_list_view(request):
    deposits = Transaction.objects.filter(user=request.user, credit=True)
    return render(request, 'list.html', {'object_list': deposits, 'list_what': 'Deposit'})

def withdrawal_list_view(request):
    withdrawals = Transaction.objects.filter(user=request.user, credit=False)
    return render(request, 'list.html', {'object_list': withdrawals, 'list_what': 'Withdrawal'})





