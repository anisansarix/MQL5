import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pandas as pd

class ForexTradingEnv(gym.Env):
    """A custom Forex trading environment for Gymnasium, optimized for Prop Firm Rules"""
    metadata = {'render_modes': ['human']}

    def __init__(self, df: pd.DataFrame, initial_balance=100000.0, max_drawdown=0.10):
        super(ForexTradingEnv, self).__init__()
        
        self.df = df
        self.initial_balance = initial_balance
        self.max_drawdown = max_drawdown
        
        # Action space: 0 (Hold/Close), 1 (Buy), 2 (Sell)
        self.action_space = spaces.Discrete(3)
        
        # State space features
        self.features = ['close', 'ema_fast', 'ema_slow', 'rsi', 'atr']
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(len(self.features),), dtype=np.float32
        )
        
        self.reset()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.balance = self.initial_balance
        self.current_position = 0 # 0=flat, 1=long, -1=short
        self.entry_price = 0.0
        self.holding_time = 0
        return self._next_observation(), {}

    def _next_observation(self):
        obs = self.df.iloc[self.current_step][self.features].values
        return np.array(obs, dtype=np.float32)

    def step(self, action):
        self.current_step += 1
        
        if self.current_step >= len(self.df) - 1:
            return self._next_observation(), 0, True, False, {}

        current_price = self.df.iloc[self.current_step]['close']
        reward = 0
        done = False
        
        # Calculate simplified equity for Drawdown check
        # Dynamic sizing: 1 standard lot (100k) for forex (< 10), 100 units for Gold/Crypto (> 10)
        point_multiplier = 100000 if current_price < 10 else 100
        current_equity = self.balance
        if self.current_position == 1:
            current_equity += (current_price - self.entry_price) * point_multiplier
        elif self.current_position == -1:
            current_equity += (self.entry_price - current_price) * point_multiplier
            
        dd = (self.initial_balance - current_equity) / self.initial_balance
        if dd > self.max_drawdown:
            reward = -1000 # Massive penalty for blowing the prop firm account
            done = True
            return self._next_observation(), reward, done, False, {}

        # Trade Execution & Reward Calculation
        # Action 0: Hold/Close, 1: Buy, 2: Sell
        
        # RISK MANAGEMENT: Force close (Action 0) if trade goes bad or is held too long
        if self.current_position != 0:
            self.holding_time += 1
            # Hard Stop Loss: If current trade is down 2% of the account
            if dd > 0.02:
                action = 0
                reward -= 50 # Penalty for hitting Stop Loss
            # Max Holding Period: 96 candles (24 hours at 15m)
            elif self.holding_time > 96:
                action = 0
                reward -= 10 # Penalty for holding too long
        else:
            self.holding_time = 0
        
        
        if action == 1: # BUY SIGNAL
            if self.current_position == -1: # Close short
                profit = (self.entry_price - current_price) * point_multiplier
                self.balance += profit
                reward += profit
            if self.current_position != 1: # Open long
                self.current_position = 1
                self.entry_price = current_price
                reward -= 2.0 # Transaction cost
                
        elif action == 2: # SELL SIGNAL
            if self.current_position == 1: # Close long
                profit = (current_price - self.entry_price) * point_multiplier
                self.balance += profit
                reward += profit
            if self.current_position != -1: # Open short
                self.current_position = -1
                self.entry_price = current_price
                reward -= 2.0 # Transaction cost
                
        elif action == 0: # CLOSE/FLAT SIGNAL
            if self.current_position == 1:
                profit = (current_price - self.entry_price) * point_multiplier
                self.balance += profit
                reward += profit
                self.current_position = 0
            elif self.current_position == -1:
                profit = (self.entry_price - current_price) * point_multiplier
                self.balance += profit
                reward += profit
                self.current_position = 0
                
        # Shaping & Penalties
        if self.current_position == 1:
            # Reward for unrealized profit
            reward += (current_price - self.entry_price) * 10
        elif self.current_position == -1:
            reward += (self.entry_price - current_price) * 10
        elif self.current_position == 0:
            # We removed the inactivity penalty because it forced the agent to take random bad trades.
            reward += 0.0
            
        return self._next_observation(), reward, done, False, {}
