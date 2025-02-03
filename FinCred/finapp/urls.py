from . import views
from django.urls import path

urlpatterns = [
       #path("", views.landing, name="landing"),
       path("", views.landing, name="landing"),
       path('signup/', views.signup_view, name='signup_view'),
       path('logout/', views.logout_view, name='logout'),
       path('login/', views.login_view, name='login'),
       path('dashboardnew/', views.dashboard, name='dashboardnew'),
       path('chart/', views.transaction_overview, name='transaction_overview'),
       path('newtransaction/', views.TransactionCreateView.as_view(), name='transaction_create'),
       path('transaction/delete/<int:pk>/', views.TransactionDeleteView.as_view(), name='transactiondelete'),
       path('newtransactions/', views.TransactionListView.as_view(), name='transaction_list'), 
       path('newbudget/', views.BudgetCreateView.as_view(), name='budget_create'),
       path('budgets/<int:pk>/delete/', views.BudgetDeleteView.as_view(), name='budget_delete'),
       path('newbudget/', views.BudgetListView.as_view(), name='budget_create'),
       path('savings_account/<int:pk>/', views.SavingsAccountDetailView.as_view(), name='savings_account'),
       path('savings_account/<int:account_id>/deposit/', views.savings_deposit, name='savings_account_deposit'),    
       path('savings_account/<int:account_id>/withdraw/', views.savings_withdraw, name='savings_account_withdraw'),
       path('createsavingsaccount/', views.create_savings_account, name='createsavingsaccount'),     
       path('emi_detail/', views.EMIListView.as_view(), name='emi_list'),
       path('emi_detail/<int:pk>/', views.EMIDetailView.as_view(), name='emi_detail'),
       path('emi_detail/create/', views.EMICreateView.as_view(), name='emi_create'),
       path('emi_detail/<int:emi_id>/payment/', views.emi_make_payment, name='emi_make_payment'),
       path('emi_detail/<int:pk>/', views.emi_detail, name='emi_detail'),    

       path('stock_list/', views.StockPortfolioListView.as_view(), name='stock_portfolio'),
       # View details for a specific stock portfolio (mapped to StockPortfolioDetailView)
       path('stock_portfolio/<int:pk>/', views.StockPortfolioDetailView.as_view(), name='stock_portfolio_detail'),

       # View details for a specific stock (mapped to stock_detail)
       path('stock_detail/<int:stock_id>/', views.stock_detail, name='stock_detail'),

       # Add a new stock to the portfolio (mapped to add_to_portfolio)
       path('portfolio/add/', views.add_to_portfolio, name='add_to_portfolio'),
       path('stock_visualization/', views.get_visualizations, name='get_visualizations'),




       # Predict future stock price (mapped to predict_stock_price)
       path('stock/<int:stock_id>/predict/', views.predict_stock_price, name='predict_stock_price'),
]
       

       
       





