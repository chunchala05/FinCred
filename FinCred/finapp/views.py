from .models import Stock
from django.shortcuts import get_object_or_404
from .models import Stock, StockPortfolio  # Ensure you import your models
from django.shortcuts import render, get_object_or_404
from django.shortcuts import get_object_or_404, redirect
from .models import StockPortfolio
from django.views.generic import ListView
from django.shortcuts import render
from datetime import datetime, timedelta
from django.http import JsonResponse
from .models import StockPortfolio, Stock
from django.views.generic import ListView, DetailView
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
# from django.http import JsonResponse
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
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from .forms import CustomUserCreationForm, TransactionForm, BudgetForm, SavingsAccountForm, EMICreateForm, StockPortfolioForm
import requests
from django.urls import reverse
from django.db.models import Sum
import json
from django.core.serializers.json import DjangoJSONEncoder
from datetime import datetime
import yfinance as yf
from .credit_score import CreditScoreCalculator


# Create your views here.
def landing(request):
    return render(request, 'landing.html')


def index(request):
    print('hello')
    return render(request, 'index.html')


# def dashboard(request):
    # return render(request, 'dashboardnew.html')


def chart(request):
    return render(request, 'chart.html')


def signup_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(
                request, "Signup successful! Welcome, you're now logged in.")
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
            # Debugging user login
            print(f"User {user.username} logged in successfully.")
            # Check if user is authenticated
            print(f"User authenticated after login: {
                  request.user.is_authenticated}")
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
    transactions = Transaction.objects.filter(user=user).order_by('-time')[:5]
    budgets = Budget.objects.filter(user=user)
    stock_portfolio = StockPortfolio.objects.filter(user=user)
    emi_loans = EMI.objects.filter(user=user)
    savings_account = SavingsAccount.objects.filter(user=user).first()
    detail = Detail.objects.filter(user=user).order_by('-date_created').first()

    # Calculate credit score
    credit_calculator = CreditScoreCalculator(user)
    credit_score = credit_calculator.calculate_credit_score()
    score_components = credit_calculator.get_score_components()

    context = {
        'user': user,
        'transactions': transactions,
        'budgets': budgets,
        'stock_portfolio': stock_portfolio,
        'emi_loans': emi_loans,
        'savings_account': savings_account,
        'detail': detail,
        'credit_score': credit_score,
        'score_components': score_components,
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
        context['transactions'] = Transaction.objects.filter(
            user=self.request.user).order_by('-time')
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
    # fields = ['details', 'amount', 'type', 'credit', 'description', 'tags']
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
        savings_account = SavingsAccount.objects.filter(
            user=self.request.user).first()
        if savings_account:
            form.instance.savings_account = savings_account

        # Now validate the form and save the instance
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
@method_decorator(csrf_protect, name='dispatch')
class TransactionDeleteView(DeleteView):
    model = Transaction
    template_name = 'transactiondelete.html'
    success_url = reverse_lazy('transaction_overview')

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        # Get the transaction to be deleted
        self.object = self.get_object()
        # Call the superclass delete method
        response = super().delete(request, *args, **kwargs)

        # Update the total expenditure in the Detail model
        detail = Detail.objects.filter(user=request.user).first()
        if detail:
            # Recalculate total expenditure
            total_expenditure = Transaction.objects.filter(user=request.user).exclude(
                type=7).aggregate(total=Sum('amount'))['total'] or 0
            detail.total_expenditure = total_expenditure
            detail.save()

        return response


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
    monthly_earnings = transactions.filter(
        type=7, time__month=current_month).aggregate(total=Sum('amount'))['total'] or 0

    # Calculate monthly expenses (excluding type 7 for 'income')
    monthly_expenses = transactions.filter(time__month=current_month).exclude(
        type=7).aggregate(total=Sum('amount'))['total'] or 0

    # Get the balance from the user's savings account
    savings_account = SavingsAccount.objects.filter(user=user).first()
    balance = savings_account.balance if savings_account else 0.0

    # Get total expenditure from details
    details = Detail.objects.filter(user=user).first()
    total_expenditure = details.total_expenditure if details else 0.0

    # Prepare data for charts (daily expenses, etc.)
    # Prepare data for charts (daily expenses, etc.)
    daily_expenses = transactions.values('time__date').annotate(
        total=Sum('amount')).order_by('time__date')

    # Prepare expense distribution by category
    expense_distribution = transactions.values(
        'type').annotate(total=Sum('amount')).order_by('type')

    # Prepare data for charts
    dates = [entry['time__date'].strftime(
        '%Y-%m-%d') for entry in daily_expenses]
    expenses = [entry['total'] for entry in daily_expenses]

    # Get category names from the categories tuple defined in your models
    categories_dict = dict(categories)
    category_names = []
    category_totals = []

    # Aggregate category totals
    for entry in expense_distribution:
        category_name = categories_dict.get(entry['type'], "Unknown")
        category_names.append(category_name)
        category_totals.append(entry['total'])

    # Remove duplicates while summing totals
    unique_categories = {}
    for name, total in zip(category_names, category_totals):
        if name in unique_categories:
            unique_categories[name] += total
        else:
            unique_categories[name] = total

    # Prepare final lists for the chart
    final_category_names = list(unique_categories.keys())
    final_category_totals = list(unique_categories.values())

    # Pass everything to context
    context = {
        'transactions': transactions,
        'selected_date': selected_date if selected_date else '',
        'monthly_earnings': monthly_earnings,
        'monthly_expenses': monthly_expenses,
        'balance': balance,
        'total_expenditure': total_expenditure,
        'dates': json.dumps(dates, cls=DjangoJSONEncoder),
        'expenses': json.dumps(expenses, cls=DjangoJSONEncoder),
        'categories': json.dumps(final_category_names, cls=DjangoJSONEncoder),
        'category_totals': json.dumps(final_category_totals, cls=DjangoJSONEncoder),
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        budget = self.object  # The specific budget object

        # Assuming you have a related model for budget items
        # Adjust this according to your model
        budget_items = budget.budgetitem_set.all()

        # Prepare data for budget allocation chart
        category_names = []
        category_totals = []

        for item in budget_items:
            # Assuming each item has a category with a name
            category_names.append(item.category.name)
            # Assuming each item has an amount
            category_totals.append(item.amount)

        # Pass data to context
        context['budget_category_names'] = json.dumps(category_names)
        context['budget_category_totals'] = json.dumps(category_totals)

        return context


@method_decorator(login_required, name='dispatch')
class BudgetCreateView(CreateView):
    model = Budget
    form_class = BudgetForm  # Use the custom form class
    template_name = 'newbudget.html'
    # Redirect to budget list after creation
    success_url = reverse_lazy('budget_create')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user  # Pass the user to the form
        return kwargs

    def get_context_data(self, **kwargs):
        # Adding additional context if necessary
        context = super().get_context_data(**kwargs)
        context['budgets'] = Budget.objects.filter(
            user=self.request.user).order_by('-date_created')
        return context


@method_decorator(login_required, name='dispatch')
class BudgetDeleteView(DeleteView):
    model = Budget
    template_name = 'budget_delete.html'
    # Redirect to budget list after deletion
    success_url = reverse_lazy('budget_create')

    def get_queryset(self):
        # Ensure the user can only delete their own budgets
        return Budget.objects.filter(user=self.request.user)


# ------------------- STOCK PORTFOLIO VIEWS -------------------
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

    @staticmethod
    def format_market_cap(market_cap):
        if market_cap is None:
            return 'N/A'

        # Convert to float if it's not already
        market_cap = float(market_cap)

        if market_cap >= 1_000_000_000_000:
            return f"{market_cap / 1_000_000_000_000:.2f} Trillion"
        elif market_cap >= 1_000_000_000:
            return f"{market_cap / 1_000_000_000:.2f} Billion"
        elif market_cap >= 1_000_000:
            return f"{market_cap / 1_000_000:.2f} Million"
        else:
            return f"{market_cap:.2f}"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Fetch Nifty 50 stock data from Yahoo Finance
        stocks_data = []
        for symbol in NIFTY_50_SYMBOLS:
            stock = yf.Ticker(symbol)
            stock_info = stock.info

            # Prepare stock data for saving
            ticker = symbol.split('.')[0]  # Extract ticker without '.NS'
            company_name = stock_info.get('longName', 'N/A')
            current_price = stock_info.get('currentPrice', 0.0)

            # Fetch historical data for the last year
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)
            historical_data = stock.history(start=start_date, end=end_date)

            # Prepare data for JSONField
            historical_records = []
            for date, row in historical_data.iterrows():
                record = {
                    "date": date.strftime('%Y-%m-%d'),
                    "open": row['Open'],
                    "close": row['Close'],
                    "high": row['High'],
                    "low": row['Low'],
                    "volume": row['Volume'],
                    "change_percentage": ((row['Close'] - row['Open']) / row['Open']) * 100 if row['Open'] != 0 else 0
                }
                historical_records.append(record)

            # Save or update stock in the database
            stock_instance, created = Stock.objects.update_or_create(
                ticker=ticker,
                defaults={
                    'company_name': company_name,
                    'current_price': current_price,
                    'historical_data': historical_records  # Store historical data in JSONField
                }
            )

            # Append the fetched data to stocks_data list
            stocks_data.append({
                'id': stock_instance.id,
                'symbol': ticker,
                'name': company_name,
                'price': current_price,
                'market_cap': self.format_market_cap(stock_info.get('marketCap', None))
            })

        context['nifty_50_stocks'] = stocks_data
        return context


@login_required
def add_to_portfolio(request, stock_id=None):
    stock = None
    current_price = None

    if stock_id:
        # Fetch the stock from the database using its ticker
        stock = get_object_or_404(Stock, ticker=stock_id)
        # Use the current price stored in the database
        current_price = stock.current_price

    if request.method == 'POST':
        form = StockPortfolioForm(request.POST)
        if form.is_valid():
            # Create a new StockPortfolio instance
            stock_portfolio = form.save(commit=False)
            stock_portfolio.user = request.user

            # Ensure that a valid stock is selected
            if stock:
                stock_portfolio.stock = stock  # Associate the selected Stock instance

            # Save the StockPortfolio instance
            stock_portfolio.save()
            return redirect('stock_portfolio')
        else:
            print(form.errors)  # Print any validation errors for debugging
    else:
        # Initialize form with current price if available
        form = StockPortfolioForm(initial={'purchase_price': current_price})

    context = {
        'form': form,
        'stocks': Stock.objects.all(),  # List of all stocks for selection if needed
        'selected_stock': stock,
        'current_price': current_price,
    }
    return render(request, 'stock_add_to_portfolio.html', context)


@login_required
def portfolio_view(request):
    portfolios = StockPortfolio.objects.filter(user=request.user)

    # Prepare data for rendering
    portfolio_data = []
    total_invested = 0
    total_current_value = 0

    for portfolio in portfolios:
        stock = portfolio.stock
        current_price = stock.current_price

        invested_amount = portfolio.shares * portfolio.purchase_price
        current_value = portfolio.shares * current_price
        gain_loss = current_value - invested_amount

        portfolio_data.append({
            'stock': stock,
            'shares': portfolio.shares,
            'purchase_price': portfolio.purchase_price,
            'current_price': current_price,
            'invested_amount': invested_amount,
            'current_value': current_value,
            'gain_loss': gain_loss,
            'portfolio_id': portfolio.id  # Include ID for deletion
        })

        total_invested += invested_amount
        total_current_value += current_value

    overall_gain_loss = total_current_value - total_invested

    context = {
        'portfolio_data': portfolio_data,
        'total_invested': total_invested,
        'total_current_value': total_current_value,
        'overall_gain_loss': overall_gain_loss,
    }

    return render(request, 'stock_portfolio.html', context)


@login_required
def delete_stock_fportfolio(request, portfolio_id):
    # Fetch the stock portfolio entry
    stock_portfolio = get_object_or_404(
        StockPortfolio, id=portfolio_id, user=request.user)

    if request.method == 'POST':
        shares_to_delete = int(request.POST.get('shares_to_delete', 0))

        if shares_to_delete <= 0 or shares_to_delete > stock_portfolio.shares:
            messages.error(request, "Invalid number of shares to delete.")
            return redirect('stock_portfolio')

        # Update shares or delete if all are removed
        if shares_to_delete < stock_portfolio.shares:
            stock_portfolio.shares -= shares_to_delete
            stock_portfolio.save()
            messages.success(request, f"Deleted {shares_to_delete} shares of {
                             stock_portfolio.stock.company_name}.")
        else:
            stock_portfolio.delete()
            messages.success(request, f"Deleted all shares of {
                             stock_portfolio.stock.company_name} from your portfolio.")

        return redirect('stock_portfolio')

    context = {
        'stock': stock_portfolio.stock,
        'current_shares': stock_portfolio.shares,
    }
    return render(request, 'stock_confirm_delete_fportfolio.html', context)


@login_required
def stock_detail_view(request, stock_id):
    stock = get_object_or_404(Stock, id=stock_id)

    # Fetch last 30 days of historical data
    historical_data = stock.historical_data[-30:]

    # Convert data to JSON for JavaScript usage
    historical_json = json.dumps(historical_data)

    context = {
        'stock': stock,
        'historical_data': historical_data,
        'historical_json': historical_json,  # JSON data for frontend
    }

    return render(request, 'stock_detail.html', context)


# ------------------- SAVINGS ACCOUNT VIEWS -------------------


@method_decorator(login_required, name='dispatch')
class SavingsAccountDetailView(DetailView):
    model = SavingsAccount
    template_name = 'savings_account.html'

    def get_queryset(self):
        return SavingsAccount.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # This is set by the DetailView
        savings_account = context['savingsaccount']
        context['savings_account'] = savings_account
        return context


@login_required
def savings_deposit(request, account_id):
    """
    Deposit funds into a savings account.
    """
    savings_account = get_object_or_404(
        SavingsAccount, id=account_id, user=request.user)
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
    savings_account = get_object_or_404(
        SavingsAccount, id=account_id, user=request.user)
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
            # Redirect to the dashboard or any other relevant page
            return redirect('dashboardnew')
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
        context['emi_loans'] = EMI.objects.filter(
            user=self.request.user).order_by('-start_date')
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
                f"Successfully paid ${amount}. Outstanding balance is now ${
                    emi.outstanding_balance}. "
                f"Savings account balance: ${
                    emi.linked_savings_account.balance if emi.linked_savings_account else 'N/A'}."
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
