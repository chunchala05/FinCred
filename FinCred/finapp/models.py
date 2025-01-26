from django.db import models
import re
import random
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractUser, Group, Permission
from datetime import datetime
from decimal import Decimal


class User(AbstractUser):
    email = models.EmailField(unique=True, null=False, blank=False)
    first_name = models.CharField(max_length=30, null=False, blank=False)
    last_name = models.CharField(max_length=30, null=False, blank=False)
    groups = models.ManyToManyField(Group, related_name='finapp_user_set', blank=True, verbose_name='groups')
    user_permissions = models.ManyToManyField(Permission, related_name='finapp_user_permissions_set', blank=True, verbose_name='user permissions')

    def total_transactions(self):
        """
        Calculate the total number of transactions for this user.
        """
        try:
            return Transaction.objects.filter(user=self).count()
        except Transaction.DoesNotExist:
            return 0

    def __str__(self):
        return self.username


class Detail(models.Model):
    """
    Model for storing Monthly Statements of Users
    """
    user = models.ForeignKey(User, verbose_name="USER", on_delete=models.CASCADE)
    income = models.DecimalField(verbose_name="INCOME", max_digits=10, decimal_places=2, default=0)
    savings = models.DecimalField(verbose_name="SAVINGS", max_digits=10, decimal_places=2, default=0)
    total_expenditure = models.DecimalField(verbose_name="TOTAL EXPENDITURE", max_digits=10, decimal_places=2, default=0)
    housing = models.DecimalField(verbose_name="HOUSING", max_digits=10, decimal_places=2, default=0)
    food = models.DecimalField(verbose_name="FOOD", max_digits=10, decimal_places=2, default=0)
    healthcare = models.DecimalField(verbose_name="HEALTHCARE", max_digits=10, decimal_places=2, default=0)
    transportation = models.DecimalField(verbose_name="TRANSPORTATION", max_digits=10, decimal_places=2, default=0)
    recreation = models.DecimalField(verbose_name="RECREATION", max_digits=10, decimal_places=2, default=0)
    others = models.DecimalField(verbose_name="OTHERS", max_digits=10, decimal_places=2, default=0)
    stock = models.DecimalField(verbose_name="STOCK", max_digits=10, decimal_places=2, default=0)
    total_transactions = models.IntegerField(verbose_name="TOTAL TRANSACTIONS", default=0)
    date_created = models.DateField(auto_now_add=True, null=True, verbose_name="DATE CREATED")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'date_created'], name='unique_user_monthly_detail')
        ]

    def __str__(self):
        return f"{self.user} / {self.get_month} / {self.get_year}"

    @property
    def get_month(self):
        return self.date_created.strftime("%m")

    @property
    def get_year(self):
        return self.date_created.strftime("%Y")

    def analyze_budget(self):
        """
        Analyze the user's budget and spending habits.
        """
        total_income = self.income
        total_expenditure = self.total_expenditure
        savings_rate = (self.savings / total_income) * 100 if total_income > 0 else 0
        expenditure_rate = (total_expenditure / total_income) * 100 if total_income > 0 else 0

        return {
            'savings_rate': savings_rate,
            'expenditure_rate': expenditure_rate,
            'remaining_budget': total_income - total_expenditure
        }


categories = [
    (0, "Income"),
    (1, "Housing"),
    (2, "Food"),
    (3, "Healthcare"),
    (4, "Transportation"),
    (5, "Recreation"),
    (6, "Other"),
    (7, 'Stock'),
]

class SavingsAccount(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='savings_accounts')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    goals = models.JSONField(default=list)
    date_created = models.DateField(auto_now_add=True, null=True, verbose_name="DATE CREATED")

    def __str__(self):
        return f"Savings account of {self.user.username} - Balance: {self.balance}"

       
    def add_deposit(self, amount):
        if amount <= 0:
            raise ValidationError("Deposit amount must be positive.")
        # Ensure the amount is a Decimal
        amount = Decimal(amount) if not isinstance(amount, Decimal) else amount
        self.balance += amount  # Add the deposit (both are Decimal now)
        self.save()

    def withdraw(self, amount):
        if self.balance < amount:
            raise ValidationError(f"Insufficient funds: You have only {self.balance} available.")
        amount = Decimal(amount) if not isinstance(amount, Decimal) else amount
        self.balance -= amount
        self.save()

    def reset_goals(self):
        self.goals.clear()
        self.save()


class Transaction(models.Model):

    user = models.ForeignKey(User, verbose_name="USER", on_delete=models.CASCADE)
    savings_account = models.ForeignKey(SavingsAccount, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Savings Account")
    details = models.ForeignKey(Detail, on_delete=models.CASCADE, verbose_name="DETAILS")
    time = models.DateTimeField(default=timezone.now, verbose_name="CREATED")
    last_updated = models.DateTimeField(auto_now=True, verbose_name="LAST UPDATED")
    amount = models.DecimalField(verbose_name="AMOUNT", max_digits=10, decimal_places=2, default=0)
    type = models.IntegerField(choices=categories, verbose_name="Type")
    credit = models.BooleanField(verbose_name="CREDIT", default=False)
    description = models.TextField(blank=True, default="Description", verbose_name="DESCRIPTION")
    tags = models.JSONField(default=list, blank=True, verbose_name="TAGS")
    date_created = models.DateField(auto_now_add=True, null=True, verbose_name="DATE CREATED")
   
    

    def __str__(self):
        return f"{self.user} / {self.time} / {self.amount} / {self.get_category()} / {self.description} / {self.credit}"

    def get_category(self):
        return dict(categories).get(self.type, "Unknown")

    @property
    def get_month(self):
        return timezone.localtime(self.time).strftime("%m")

    @property
    def get_year(self):
        return timezone.localtime(self.time).strftime("%Y")
    
    def save(self, *args, **kwargs):
    # Ensure that user is set before saving
        if not self.user:
            raise ValueError("User is required for saving a transaction.")

        # Proceed with the rest of the save logic
        is_new = self.pk is None
        previous_amount = 0
        previous_type = None

        if not is_new:
            old_transaction = Transaction.objects.get(pk=self.pk)
            previous_amount = old_transaction.amount
            previous_type = old_transaction.type

        # Update savings account balance
        if self.savings_account:
            if self.credit:
                self.savings_account.add_deposit(self.amount)
            else:
                self.savings_account.withdraw(self.amount)

        super().save(*args, **kwargs)

        # Update related detail instance
        detail = self.details

        if is_new:
            detail.total_transactions += 1
            detail.total_expenditure += 0 if self.credit else self.amount
            if not self.credit:
                self._update_category_field(detail, self.type, self.amount)
        else:
            if previous_type is not None:
                self._update_category_field(detail, previous_type, -previous_amount)
            if not self.credit:
                self._update_category_field(detail, self.type, self.amount - previous_amount)

        detail.savings = detail.income - detail.total_expenditure
        detail.save()


    def delete(self, *args, **kwargs):
        """
        Override delete method to update savings account and detail instance.
        """
        if self.savings_account:
            if self.credit:
                self.savings_account.withdraw(self.amount)  # Reverse deposit
            else:
                self.savings_account.add_deposit(self.amount)  # Reverse withdrawal

        # Update related detail instance
        detail = self.details
        detail.total_transactions -= 1
        detail.total_expenditure -= 0 if self.credit else self.amount
        self._update_category_field(detail, self.type, -self.amount)
        detail.savings = detail.income - detail.total_expenditure
        detail.save()

        super().delete(*args, **kwargs)

    def _update_category_field(self, detail, category_type, amount):
        """
        Update the appropriate field in the Detail model based on transaction type.
        """
        category_map = {
            1: 'housing',
            2: 'food',
            3: 'healthcare',
            4: 'transportation',
            5: 'recreation',
            6: 'others',
            7: 'stock'
        }
        field_name = category_map.get(category_type)
        if field_name:
            setattr(detail, field_name, getattr(detail, field_name) + amount)

    def clean(self):
        """
        Validate transaction data before saving.
        """
        # Check if the user owns the details
        #if self.details.user != self.user:
            #raise ValidationError(_('User does not own this Detail.'))

        # Get the current month and year using timezone-aware datetime
        current_month = timezone.now().strftime("%m")
        current_year = timezone.now().strftime("%Y")

        # Compare the current month and year with those in self.details
        if (self.details.get_month != current_month) or (self.details.get_year != current_year):
            raise ValidationError(_('Time of transaction and details do not match.'))


    def analyze_spending(self):
        """
        Analyze spending habits based on transaction data.
        """
        total_spent = Transaction.objects.filter(user=self.user).aggregate(total=Sum('amount'))['total'] or 0
        return {
            'total_spent': total_spent,
            'average_spent': total_spent / self.details.total_transactions if self.details.total_transactions > 0 else 0,
            'spending_by_category': self.get_spending_by_category()
        }

    def get_spending_by_category(self):
        """
        Get spending breakdown by category.
        """
        spending_breakdown = {category[1]: 0 for category in categories}
        transactions = Transaction.objects.filter(user=self.user)
        for transaction in transactions:
            spending_breakdown[transaction.get_category()] += transaction.amount
        return spending_breakdown


class Budget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='budgets')
    category = models.IntegerField(choices=categories, verbose_name="Category")
    limit = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Budget Limit")
    date_created = models.DateField(auto_now_add=True)
    end_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.get_category_display()} Budget: {self.limit}"

    def is_within_budget(self, amount):
        """
        Check if the amount is within the budget limit.
        """
        return amount <= self.limit


class Stock(models.Model):
    ticker = models.CharField(max_length=10, unique=True)
    company_name = models.CharField(max_length=255)
    current_price = models.FloatField()
    historical_data = models.JSONField(default=list)

    def __str__(self):
        return self.company_name

    def predict_price(self):
        """
        Placeholder for predicting future stock prices.
        """
        if not self.historical_data:
            return self.current_price

        future_price = self.historical_data[-1][1] * random.uniform(0.95, 1.05)
        return future_price


class StockPortfolio(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stock_portfolio')
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE)
    shares = models.FloatField(default=0)
    purchase_price = models.FloatField()

    @property
    def current_value(self):
        return self.shares * self.stock.current_price

    def clean(self):
        if self.purchase_price < 0:
            raise ValidationError("Purchase price cannot be negative.")

    def __str__(self):
        return f"{self.user.username} - {self.stock.ticker}"


class EMI(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='loans')
    loan_amount = models.FloatField(verbose_name="Loan Amount")
    interest_rate = models.FloatField(verbose_name="Interest Rate (%)")
    tenure_months = models.IntegerField(verbose_name="Tenure (in months)")
    start_date = models.DateField(verbose_name="Start Date")
    paid_amount = models.FloatField(default=0, verbose_name="Amount Paid")
    linked_savings_account = models.ForeignKey(SavingsAccount, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Linked Savings Account"
    )

    @property
    def monthly_payment(self):
        """Calculate monthly EMI payment"""
        P = self.loan_amount  # Principal amount
        R = self.interest_rate / (12 * 100)  # Monthly interest rate
        N = self.tenure_months  # Total number of months
        
        # EMI calculation formula: P * R * (1 + R)^N / ((1 + R)^N - 1)
        if R == 0:  # Handle zero interest case
            return P / N
        
        emi = P * R * (1 + R)**N / ((1 + R)**N - 1)
        return round(emi, 2)

    @property
    def total_payable(self):
        return round(self.monthly_payment * self.tenure_months, 2)

    @property
    def outstanding_balance(self):
        total_payable = self.monthly_payment * self.tenure_months
        return round(total_payable - self.paid_amount, 2)

    def make_payment(self, amount):
        if amount <= 0:
            raise ValidationError("Payment amount must be positive.")
        if amount > self.outstanding_balance:
            raise ValidationError("Payment exceeds the outstanding balance.")

        if self.linked_savings_account:
            if self.linked_savings_account.balance < amount:
                raise ValidationError("Insufficient funds in the linked savings account.")
            self.linked_savings_account.withdraw(amount)

        self.paid_amount += amount
        self.save()


    def __str__(self):
        return f"Loan for {self.user.username} - Outstanding: {self.outstanding_balance}"



