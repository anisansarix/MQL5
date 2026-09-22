import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from risk_manager.prop_firm_guard import PropFirmGuard

class MockTick:
    def __init__(self, time_val):
        self.time = time_val

@patch('risk_manager.prop_firm_guard.mt5')
def test_get_daily_trades_count_uses_server_time(mock_mt5):
    guard = PropFirmGuard(initial_balance=100000.0)
    
    # Mock a server tick at 2026-09-22 00:01:00 UTC (start of a new day)
    # Using explicit UTC timestamp to avoid local timezone issues in testing
    # 1790035260 is 2026-09-22 00:01:00 UTC
    mock_mt5.symbol_info_tick.return_value = MockTick(1790035260)
    
    # We just want to ensure history_deals_get is called with the correct server 'today' boundary
    mock_mt5.history_deals_get.return_value = []
    
    guard.get_daily_trades_count()
    
    # Assert that history_deals_get was called with today = 2026-09-22 00:00:00
    called_args = mock_mt5.history_deals_get.call_args[0]
    called_today = called_args[0]
    
    assert called_today == datetime(2026, 9, 22, 0, 0, 0)
