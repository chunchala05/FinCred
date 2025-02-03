import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import joblib
import os
from datetime import datetime, timedelta
from django.conf import settings
from .models import Transaction, EMI, SavingsAccount, models
from django.utils import timezone

class CreditScoreCalculator:
    def __init__(self, user):
        self.user = user
        # Create model directory in the project's base directory
        self.model_dir = os.path.join(settings.BASE_DIR, 'finapp', 'ml_models')
        self.model_path = os.path.join(self.model_dir, 'credit_score_model.joblib')
        self.scaler_path = os.path.join(self.model_dir, 'credit_score_scaler.joblib')
        
        # Create directory if it doesn't exist
        os.makedirs(self.model_dir, exist_ok=True)
        
        self._load_or_train_model()

    def _generate_training_data(self, n_samples=1000):
        """Generate synthetic training data for the credit score model"""
        np.random.seed(42)
        
        # Generate random features
        payment_history = np.random.uniform(0, 1, n_samples)  # 0 = bad, 1 = perfect
        credit_utilization = np.random.uniform(0, 100, n_samples)  # percentage
        account_age = np.random.uniform(0, 120, n_samples)  # months
        savings_ratio = np.random.uniform(0, 1, n_samples)  # savings/income ratio
        emi_payment_ratio = np.random.uniform(0, 1, n_samples)  # EMI payments/income ratio
        
        X = np.column_stack([
            payment_history,
            credit_utilization,
            account_age,
            savings_ratio,
            emi_payment_ratio
        ])
        
        # Generate credit scores based on features
        y = (payment_history * 300 +  # 30% weight
             (100 - credit_utilization) * 1.5 +  # 15% weight
             account_age * 1.0 +  # 10% weight
             savings_ratio * 250 +  # 25% weight
             (1 - emi_payment_ratio) * 200  # 20% weight
            )
        
        # Add some noise
        y += np.random.normal(0, 20, n_samples)
        
        # Clip scores to valid range
        y = np.clip(y, 300, 850)
        
        return X, y

    def _load_or_train_model(self):
        """Load existing model or train a new one if not exists"""
        try:
            self.model = joblib.load(self.model_path)
            self.scaler = joblib.load(self.scaler_path)
        except:
            # Train new model
            X, y = self._generate_training_data()
            
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            
            self.model = RandomForestRegressor(n_estimators=100, random_state=42)
            self.model.fit(X_scaled, y)
            
            # Save model and scaler
            joblib.dump(self.model, self.model_path)
            joblib.dump(self.scaler, self.scaler_path)

    def _calculate_payment_history(self):
        """Calculate payment history score based on transaction records"""
        six_months_ago = timezone.now() - timedelta(days=180)
        transactions = Transaction.objects.filter(
            user=self.user,
            time__gte=six_months_ago
        )
        
        if not transactions.exists():
            return 0.5  # Default score for new users
        
        total_transactions = transactions.count()
        on_time_payments = transactions.filter(credit=True).count()
        
        return on_time_payments / total_transactions if total_transactions > 0 else 0.5

    def _calculate_credit_utilization(self):
        """Calculate credit utilization ratio"""
        savings_account = SavingsAccount.objects.filter(user=self.user).first()
        if not savings_account:
            return 50  # Default middle value
        
        total_credit = savings_account.balance

        emis = EMI.objects.filter(user=self.user)
        used_credit = sum(emi.outstanding_balance for emi in emis)
        
        if total_credit == 0:
            return 50
        
        utilization = (used_credit / float(total_credit)) * 100
        return min(utilization,100)

    def _calculate_account_age(self):
        """Calculate account age in months"""
        user_date_joined = self.user.date_joined
        months = (timezone.now().date() - user_date_joined.date()).days / 30
        return months

    def _calculate_savings_ratio(self):
        """Calculate savings to income ratio"""
        savings_account = SavingsAccount.objects.filter(user=self.user).first()
        if not savings_account:
            return 0.5
        
        total_income = Transaction.objects.filter(
            user=self.user,
            credit=True,
            type=7  # Assuming 7 is income type
        ).aggregate(total=models.Sum('amount'))['total'] or 1
        
        return min(savings_account.balance / total_income, 1) if total_income > 0 else 0.5

    def _calculate_emi_payment_ratio(self):
        """Calculate EMI payments to income ratio"""
        # Get all EMIs for the user
        emis = EMI.objects.filter(user=self.user)
        total_emi = sum(emi.monthly_payment for emi in emis)
        
        # Calculate monthly income from transactions
        monthly_income = Transaction.objects.filter(
            user=self.user,
            credit=True,
            type=7  # Assuming 7 is income type
        ).aggregate(total=models.Sum('amount'))['total'] or 1
        
        return min(total_emi / monthly_income, 1) if monthly_income > 0 else 0.5

    def calculate_credit_score(self):
        """Calculate final credit score"""
        features = np.array([
            self._calculate_payment_history(),
            self._calculate_credit_utilization(),
            self._calculate_account_age(),
            self._calculate_savings_ratio(),
            self._calculate_emi_payment_ratio()
        ]).reshape(1, -1)
        
        features_scaled = self.scaler.transform(features)
        predicted_score = self.model.predict(features_scaled)[0]
        
        return int(round(predicted_score))

    def get_score_components(self):
        """Get detailed breakdown of credit score components"""
        return {
            'payment_history': self._calculate_payment_history() * 100,
            'credit_utilization': self._calculate_credit_utilization(),
            'account_age': self._calculate_account_age(),
            'savings_ratio': self._calculate_savings_ratio() * 100,
            'emi_payment_ratio': self._calculate_emi_payment_ratio() * 100
        } 