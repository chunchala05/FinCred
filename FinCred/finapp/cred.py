import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

# Sample dataset structure (customize based on actual data)
data = pd.DataFrame({
    'user_age': [25, 45, 30, 35, 40],               # Age of user
    'monthly_income': [3000, 7000, 5000, 4500, 6000],  # Monthly income
    'monthly_expense': [1500, 3000, 2000, 2500, 2700],  # Monthly expenses
    'emi_count': [1, 3, 2, 1, 4],                    # Number of EMIs
    'stock_investment': [5000, 15000, 10000, 8000, 12000],  # Investment in stocks
    'savings_account_balance': [2000, 8000, 3000, 5000, 7000],  # Savings account balance
    'transaction_count': [20, 35, 25, 30, 40],       # Monthly transaction count
    'credit_score': [650, 720, 680, 700, 750]        # Target variable (Credit Score)
})

# Separating features (X) and target variable (y)
X = data.drop(columns=['credit_score'])
y = data['credit_score']

# Standardizing the features
scaler = StandardScaler()
X = scaler.fit_transform(X)

# Splitting the data into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Initializing and training the Random Forest Regressor
model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Predicting on the test set
y_pred = model.predict(X_test)

# Evaluating the model
mse = mean_squared_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print("Mean Squared Error:", mse)
print("R-squared Score:", r2)

# Feature importance
feature_importance = model.feature_importances_
features = data.columns[:-1]  # Exclude 'credit_score'
feature_importance_df = pd.DataFrame({
    'Feature': features,
    'Importance': feature_importance
}).sort_values(by='Importance', ascending=False)

print("\nFeature Importance:")
print(feature_importance_df)


