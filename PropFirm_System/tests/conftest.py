import pytest
from unittest.mock import MagicMock
import sys
import os

# Create a mock for MetaTrader5
mt5_mock = MagicMock()
mt5_mock.DEAL_ENTRY_IN = 0
mt5_mock.DEAL_ENTRY_OUT = 1
sys.modules['MetaTrader5'] = mt5_mock

@pytest.fixture(autouse=True)
def reset_mocks():
    mt5_mock.reset_mock()
    yield
