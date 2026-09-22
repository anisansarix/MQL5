import pytest
from unittest.mock import patch, MagicMock
from risk_manager.prop_firm_guard import PropFirmGuard

class MockAccountInfo:
    def __init__(self, balance, equity):
        self.balance = balance
        self.equity = equity

@patch('risk_manager.prop_firm_guard.mt5')
def test_risk_limits_dynamic_update(mock_mt5):
    # Set up initial state
    mock_mt5.account_info.return_value = MockAccountInfo(balance=100000.0, equity=100000.0)
    mock_mt5.history_deals_get.return_value = [] # No trades today
    
    guard = PropFirmGuard(initial_balance=100000.0, max_daily_loss_pct=0.05, max_trailing_dd_pct=0.10)
    
    # 1. Normal trading allowed
    assert guard.check_risk_status() == True
    
    # 2. Equity drops by 6% (Breaches 5% daily limit)
    mock_mt5.account_info.return_value = MockAccountInfo(balance=100000.0, equity=94000.0)
    assert guard.check_risk_status() == False
    
    # 3. Increase daily loss limit to 10% dynamically (as config.json might do)
    guard.max_daily_loss_pct = 0.10
    assert guard.check_risk_status() == True
    
    # 4. Equity drops by 11% (Breaches 10% total DD)
    mock_mt5.account_info.return_value = MockAccountInfo(balance=100000.0, equity=89000.0)
    assert guard.check_risk_status() == False
