import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pandas as pd

class ForexTradingEnv(gym.Env):
    """A custom Forex trading environment with Continuous Actions, optimized for Prop Firm Rules"""
    metadata = {'render_modes': ['human']}

    def __init__(self, df: pd.DataFrame, initial_balance=25000.0, max_drawdown=0.12, daily_drawdown=0.04):
        super(ForexTradingEnv, self).__init__()
        
        self.df = df
        self.initial_balance = initial_balance
        self.max_drawdown = max_drawdown
        self.daily_drawdown = daily_drawdown
        
        # Action space: Continuous [-1.0, 1.0] representing target position (-1=Max Short, 1=Max Long)
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(1,), dtype=np.float32)
        
        # State space features
        self.features = ['close_norm', 'ema_fast_norm', 'ema_slow_norm', 'rsi_norm', 'atr_norm']
        # Observation is features + current_position
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(len(self.features) + 1,), dtype=np.float32
        )
        
        self.reset()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.balance = self.initial_balance
        self.equity = self.initial_balance
        self.start_of_day_balance = self.initial_balance
        self.highest_equity = self.initial_balance
        self.current_position = 0.0 # Float between -1 and 1
        return self._next_observation(), {}

    def _next_observation(self):
        obs = list(self.df.iloc[self.current_step][self.features].values)
        obs.append(self.current_position)
        return np.array(obs, dtype=np.float32)

    def step(self, action):
        prev_price = self.df.iloc[self.current_step]['close']
        self.current_step += 1
        
        if self.current_step >= len(self.df) - 1:
            return self._next_observation(), 0, True, False, {}

        current_price = self.df.iloc[self.current_step]['close']
        
        # Target position from RL action
        target_position = float(np.clip(action[0], -1.0, 1.0))
        
        # Calculate dynamic point multiplier based on leverage and risk bounds
        # For XAUUSD at 2500, a standard lot is 100oz. 1:30 leverage.
        # Let's say max risk dictates 3 standard lots. We'll simplify to 300 units max.
        point_multiplier = 300 if current_price > 1000 else 100000 
        
        # Calculate PnL from previous step to current step based on PREVIOUS position
        price_diff = current_price - prev_price
        step_pnl = self.current_position * price_diff * point_multiplier
        
        self.balance += step_pnl
        self.equity = self.balance
        
        # Update high water mark
        if self.equity > self.highest_equity:
            self.highest_equity = self.equity
            
        # Transaction costs for changing position size
        pos_change = abs(target_position - self.current_position)
        tx_cost = pos_change * 2.0 # $2 per full max lot traded
        self.balance -= tx_cost
        self.equity -= tx_cost
        
        # Apply the target position for the next step
        self.current_position = target_position
        
        # Reward is the net step PnL
        reward = step_pnl - tx_cost
        done = False
        
        # Risk Management Checks
        # Max Drawdown
        max_dd_pct = (self.highest_equity - self.equity) / self.highest_equity
        if max_dd_pct > self.max_drawdown:
            reward -= 1000 # Blown account
            done = True
            
        # Hard coded 10% Profit Target Goal
        target_equity = self.initial_balance * 1.10
        if self.equity >= target_equity:
            reward += 1000 # Prop firm passed!
            done = True
            
        return self._next_observation(), reward, done, False, {}
