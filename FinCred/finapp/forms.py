from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError
from .models import User, Transaction, Detail, Budget, EMI, SavingsAccount, StockPortfolio , categories
import requests
from django.utils.translation import gettext_lazy as _


# ------------------- USER FORMS -------------------

class CustomUserCreationForm(UserCreationForm):
    
    class Meta:
        model = User
        fields = ['username','email','first_name','last_name','password1','password2']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email


class LoginForm(AuthenticationForm):
    """
    Form for user login.
    """
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))


# ------------------- TRANSACTION FORMS -------------------

class TransactionForm(forms.ModelForm):
    """
    Form for creating and updating transactions.
    """
    class Meta:
        model = Transaction
        fields = ['details', 'amount', 'type', 'credit', 'description', 'tags']
        
        widgets = {
            'details': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Enter amount'}),
            'type': forms.Select(choices=categories, attrs={'class': 'form-select'}),
            'credit': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Enter description'}),
            'tags': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter tags (comma-separated)'}),
        }
    

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.user:
            self.fields['details'].queryset = Detail.objects.filter(user=self.user)
            self.fields['savings_account'] = forms.ModelChoiceField(
                queryset=SavingsAccount.objects.filter(user=self.user),
                required=False,
                help_text="Select a savings account (optional)."
            )

    def clean(self):
        cleaned_data = super().clean()
        details = cleaned_data.get('details')
        
        if self.user and details and details.user != self.user:
            #raise ValidationError(_("You don't have permission to use this detail."))
            return cleaned_data

    def form_valid(self, form):
        print(f"Request user: {self.request.user}")  # Check the user from the request
    # Set the user for the transaction instance
        form.instance.user = self.request.user
        print(f"User  set to: {form.instance.user}")  # Debugging line
        
        # Ensure a savings account is set if available
        savings_account = SavingsAccount.objects.filter(user=self.request.user).first()
        if savings_account:
            form.instance.savings_account = savings_account
        
        # Now validate the form and save the instance
        return super().form_valid(form)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user  # Pass the user to the form
        return kwargs


    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount <= 0:
            raise ValidationError("Amount must be greater than zero.")
        return amount



# ------------------- DETAIL FORMS -------------------

class DetailForm(forms.ModelForm):
    """
    Form for creating or updating monthly details.
    """
    class Meta:
        model = Detail
        fields = [
            'income', 'savings', 'total_expenditure', 'housing',
            'food', 'healthcare', 'transportation', 'recreation', 'others', 'stock'
        ]

    def clean_total_expenditure(self):
        total_expenditure = self.cleaned_data.get('total_expenditure')
        income = self.cleaned_data.get('income', 0)
        if total_expenditure > income:
            raise ValidationError("Total expenditure cannot exceed income.")
        return total_expenditure


# ------------------- BUDGET FORMS -------------------

class BudgetForm(forms.ModelForm):
    """
    Form for creating or updating budgets.
    """
    class Meta:
        model = Budget
        fields = ['category', 'limit']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)  # Extract the user from kwargs
        super().__init__(*args, **kwargs)

    def clean_limit(self):
        limit = self.cleaned_data.get('limit')
        if limit <= 0:
            raise ValidationError("Budget limit must be greater than zero.")
        return limit

    def save(self, commit=True):
        # Set the user before saving the budget instance
        instance = super().save(commit=False)
        instance.user = self.user  # Assign the user
        if commit:
            instance.save()
        return instance


# ------------------- EMI FORMS -------------------

class EMICreateForm(forms.ModelForm):
    """
    Form for creating a new EMI loan.
    """
    class Meta:
        model = EMI
        fields = ['loan_amount', 'interest_rate', 'tenure_months', 'start_date', 'paid_amount','linked_savings_account']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        self.fields['linked_savings_account'].queryset = SavingsAccount.objects.filter(user=user)

    def clean_interest_rate(self):
        interest_rate = self.cleaned_data.get('interest_rate')
        if interest_rate < 0:
            raise forms.ValidationError("Interest rate cannot be negative.")
        return interest_rate

    def clean_tenure_months(self):
        tenure_months = self.cleaned_data.get('tenure_months')
        if tenure_months <= 0:
            raise forms.ValidationError("Tenure must be at least one month.")
        return tenure_months

class EMIPaymentForm(forms.Form):
    """
    Form for making EMI payments.
    """
    amount = forms.DecimalField(min_value=0.01, max_digits=10, decimal_places=2, widget=forms.NumberInput(attrs={'class': 'form-control'}))

    def __init__(self, emi, *args, **kwargs):
        self.emi = emi
        super().__init__(*args, **kwargs)

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount > self.emi.outstanding_balance:
            raise ValidationError(f"Payment exceeds the outstanding balance of ${self.emi.outstanding_balance}.")
        return amount


# ------------------- SAVINGS ACCOUNT FORMS -------------------

class SavingsAccountForm(forms.ModelForm):
    """
    Form for creating or updating a savings account.
    """
    class Meta:
        model = SavingsAccount
        fields = ['balance', 'goals']
        widgets = {
            'goals': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Enter your savings goals as a list'}),
        }

    def clean_balance(self):
        balance = self.cleaned_data.get('balance')
        if balance < 0:
            raise ValidationError("Balance cannot be negative.")
        return balance 


class SavingsDepositForm(forms.Form):
    """
    Form for depositing money into a savings account.
    """
    amount = forms.DecimalField(min_value=0.01, max_digits=10, decimal_places=2, widget=forms.NumberInput(attrs={'class': 'form-control'}))


class SavingsWithdrawForm(forms.Form):
    """
    Form for withdrawing money from a savings account.
    """
    amount = forms.DecimalField(min_value=0.01, max_digits=10, decimal_places=2, widget=forms.NumberInput(attrs={'class': 'form-control'}))

    def __init__(self, savings_account, *args, **kwargs):
        self.savings_account = savings_account
        super().__init__(*args, **kwargs)

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount > self.savings_account.balance:
            raise ValidationError(f"Insufficient funds. Available balance: ${self.savings_account.balance}.")
        return amount


class StockPortfolioForm(forms.ModelForm):
    class Meta:
        model = StockPortfolio
        fields = ['stock', 'shares', 'purchase_price']

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields['purchase_price'].widget.attrs['readonly'] = True