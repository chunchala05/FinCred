from django.contrib import admin

# Register your models here.
from .models import User, Detail, Transaction, Budget, Stock, StockPortfolio, EMI, SavingsAccount

admin.site.register(User)
admin.site.register(Transaction)
admin.site.register(Budget)
admin.site.register(Detail)
admin.site.register(Stock)
admin.site.register(StockPortfolio)
admin.site.register(EMI)
admin.site.register(SavingsAccount)
