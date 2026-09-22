import pytest
from unittest.mock import patch, MagicMock
from risk_manager.prop_firm_guard import PropFirmGuard

class MockSymbolInfo:
    def __init__(self):
        self.trade_tick_size = 0.25 # Tick size for index e.g., US500
        self.trade_tick_value = 1.0
        self.point = 0.01 # Point size differs from tick size!
        self.volume_min = 0.01
        self.volume_max = 100.0
        self.volume_step = 0.01
        self.trade_contract_size = 100.0

@patch('risk_manager.prop_firm_guard.mt5')
def test_calculate_position_size_tick_size_differs_from_point(mock_mt5):
    mock_mt5.symbol_info.return_value = MockSymbolInfo()
    mock_mt5.account_info.return_value = MagicMock(margin_free=100000.0)
    mock_mt5.symbol_info_tick.return_value = MagicMock(ask=4000.0)
    
    guard = PropFirmGuard(initial_balance=100000.0)
    
    sl_distance_price = 10.0
    lot_size = guard.calculate_position_size("US500", 500.0, sl_distance_price)
    assert lot_size == 12.5

@patch('risk_manager.prop_firm_guard.mt5')
def test_calculate_position_size_below_min(mock_mt5):
    symbol_info = MockSymbolInfo()
    symbol_info.volume_min = 1.0
    mock_mt5.symbol_info.return_value = symbol_info
    mock_mt5.account_info.return_value = MagicMock(margin_free=100000.0)
    mock_mt5.symbol_info_tick.return_value = MagicMock(ask=4000.0)
    
    guard = PropFirmGuard(initial_balance=100000.0)
    # Risk is very small ($10), SL distance = 10.0
    # loss_per_lot = (10.0 / 0.25) * 1.0 = 40.0
    # target_lot_size = 10.0 / 40.0 = 0.25
    # 0.25 is below volume_min (1.0), so it should return 0.0
    
    lot_size = guard.calculate_position_size("US500", 10.0, 10.0)
    assert lot_size == 0.0
