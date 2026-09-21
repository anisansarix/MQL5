"use client";

import { useEffect, useState, useRef } from "react";
import axios from "axios";
import { LayoutDashboard, List, Clock, Gauge, Settings, Shield, MoreVertical, CircleDot } from "lucide-react";
import { createChart, IChartApi, ISeriesApi, CandlestickData, Time, ColorType } from "lightweight-charts";

export default function Home() {
  const [state, setState] = useState<any>(null);
  const [config, setConfig] = useState<any>(null);
  const [chartData, setChartData] = useState<any[]>([]);
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [countdownStr, setCountdownStr] = useState<string>("");
  
  const [activeTab, setActiveTab] = useState<'positions' | 'history'>('positions');
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);

  // Fetch State & Config
  useEffect(() => {
    const fetchStateAndConfig = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || '/api';
        const apiKey = process.env.NEXT_PUBLIC_API_KEY || 'dev_secret_key_change_me_in_production';
        const headers = { 'X-API-Key': apiKey };
        
        const [stateRes, configRes] = await Promise.all([
          axios.get(`${apiUrl}/state`, { headers }),
          axios.get(`${apiUrl}/config`, { headers })
        ]);
        
        setState(stateRes.data);
        setConfig(configRes.data);
      } catch (err) {
        console.error("Error fetching state or config", err);
      }
    };
    
    fetchStateAndConfig();
    const interval = setInterval(fetchStateAndConfig, 3000);
    return () => clearInterval(interval);
  }, []);

  // Update Countdown Timer
  useEffect(() => {
    if (!state || !state.next_run_time) return;
    
    const tick = () => {
      const remaining = state.next_run_time - (Date.now() / 1000);
      if (remaining <= 0) {
        setCountdownStr("Analyzing...");
      } else {
        const m = Math.floor(remaining / 60);
        const s = Math.floor(remaining % 60);
        setCountdownStr(`Next scan in ${m}m ${s}s`);
      }
    };
    
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [state?.next_run_time]);

  // Fetch Chart Data
  useEffect(() => {
    if (!config) return;
    
    const fetchChart = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || '/api';
        const apiKey = process.env.NEXT_PUBLIC_API_KEY || 'dev_secret_key_change_me_in_production';
        
        const symbol = config.symbols_to_trade?.[0] || 'XAUUSD';
        const tf = config.timeframe || 15;
        
        const res = await axios.get(`${apiUrl}/chart?symbol=${symbol}&timeframe=${tf}&count=200`, { 
          headers: { 'X-API-Key': apiKey } 
        });
        setChartData(res.data.data);
      } catch (err) {
        console.error("Error fetching chart data", err);
      }
    };
    fetchChart();
  }, [config?.symbols_to_trade, config?.timeframe]);

  // Chart Rendering
  useEffect(() => {
    if (!chartContainerRef.current || chartData.length === 0) return;

    if (!chartRef.current) {
      const chart = createChart(chartContainerRef.current, {
        layout: {
          background: { type: ColorType.Solid, color: 'transparent' },
          textColor: '#A0A0A0',
        },
        grid: {
          vertLines: { color: 'rgba(42, 42, 42, 0.5)' },
          horzLines: { color: 'rgba(42, 42, 42, 0.5)' },
        },
        timeScale: {
          timeVisible: true,
          secondsVisible: false,
        },
      });

      const candlestickSeries = chart.addCandlestickSeries({
        upColor: '#00cc96',
        downColor: '#ff4b4b',
        borderVisible: false,
        wickUpColor: '#00cc96',
        wickDownColor: '#ff4b4b',
      });

      chartRef.current = chart;
      seriesRef.current = candlestickSeries as any;
    }

    const formattedData: CandlestickData<Time>[] = chartData.map(d => ({
      time: d.time as Time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));

    seriesRef.current?.setData(formattedData);
    chartRef.current.timeScale().fitContent();

  }, [chartData]);

  // Bot Status Toggle
  const toggleBotStatus = async () => {
    if (!config) return;
    setIsUpdatingStatus(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || '/api';
      const apiKey = process.env.NEXT_PUBLIC_API_KEY || 'dev_secret_key_change_me_in_production';
      const newStatus = config.bot_status === 'running' ? 'stopped' : 'running';
      const updatedConfig = { ...config, bot_status: newStatus };
      
      await axios.post(`${apiUrl}/config`, updatedConfig, { 
        headers: { 'X-API-Key': apiKey } 
      });
      setConfig(updatedConfig);
    } catch (err) {
      console.error("Failed to update bot status", err);
    }
    setIsUpdatingStatus(false);
  };

  if (!state || !config) {
    return <div className="min-h-screen bg-[#121212] flex items-center justify-center text-white">Connecting to FastAPI Engine...</div>;
  }

  // Extracted Metrics
  const balance = state.balance || 0;
  const equity = state.equity || 0;
  const sod = state.start_of_day_balance || balance;
  const hw = state.highest_equity || equity;
  
  const dailyDD = sod > 0 ? Math.max(0, ((sod - equity) / sod) * 100) : 0;
  const maxDD = hw > 0 ? Math.max(0, ((hw - equity) / hw) * 100) : 0;

  const maxDailyLimitPct = config.max_daily_loss_pct ? (config.max_daily_loss_pct * 100).toFixed(0) : 5;
  const maxTrailingLimitPct = config.max_trailing_dd_pct ? (config.max_trailing_dd_pct * 100).toFixed(0) : 10;

  const positions = state.positions || [];
  const history = state.history || [];
  const openPnl = positions.reduce((acc: number, p: any) => acc + p.profit, 0);

  return (
    <div className="min-h-screen bg-[#121212] text-white flex flex-col md:flex-row p-4 gap-4">
      {/* Sidebar - hidden on mobile, visible on desktop */}
      <div className="hidden md:flex w-16 flex-shrink-0 border-r border-[#2a2a2a] flex-col items-center py-4 gap-4 bg-[#1a1a1a] rounded-xl">
        <div className="w-8 h-8 rounded-lg bg-[#378ADD] flex items-center justify-center mb-4">
          <Shield size={18} />
        </div>
        <button className="w-10 h-10 rounded-lg bg-[#2a2a2a] text-white flex items-center justify-center"><LayoutDashboard size={18} /></button>
        <button className="w-10 h-10 rounded-lg text-gray-500 hover:text-white flex items-center justify-center"><List size={18} /></button>
        <button className="w-10 h-10 rounded-lg text-gray-500 hover:text-white flex items-center justify-center"><Clock size={18} /></button>
        <button className="w-10 h-10 rounded-lg text-gray-500 hover:text-white flex items-center justify-center"><Gauge size={18} /></button>
        <div className="mt-auto">
          <button className="w-10 h-10 rounded-lg text-gray-500 hover:text-white flex items-center justify-center"><Settings size={18} /></button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-4">
          <div>
            <h1 className="text-xl font-semibold">Command Center</h1>
            <p className="text-sm text-gray-400 mt-1">Strategy • {config.strategy || 'Unknown'} • ${sod.toLocaleString(undefined, {minimumFractionDigits: 0})}</p>
          </div>
          <div className="flex items-center gap-3 w-full md:w-auto">
            <span className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md font-medium ${config.bot_status === 'running' ? 'text-[#00cc96] bg-[#00cc96]/10' : 'text-gray-400 bg-[#2a2a2a]'}`}>
              <CircleDot size={12} fill="currentColor" /> {config.bot_status === 'running' ? 'Live' : 'Paused'}
            </span>
            <button 
              onClick={toggleBotStatus}
              disabled={isUpdatingStatus}
              className={`flex-1 md:flex-none text-sm px-4 py-2 rounded-lg border transition-colors ${
                config.bot_status === 'running' 
                  ? 'bg-[#ff4b4b]/10 text-[#ff4b4b] border-[#ff4b4b]/20 hover:bg-[#ff4b4b]/20' 
                  : 'bg-[#00cc96]/10 text-[#00cc96] border-[#00cc96]/20 hover:bg-[#00cc96]/20'
              }`}
            >
              {isUpdatingStatus ? 'Updating...' : (config.bot_status === 'running' ? 'Stop Engine' : 'Start Engine')}
            </button>
            <button className="p-2 text-gray-400 hover:text-white shrink-0"><MoreVertical size={18} /></button>
          </div>
        </div>

        {/* Top 4 Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-5 text-center flex flex-col justify-center">
            <p className="text-sm text-gray-400 mb-2">Daily loss limit</p>
            <p className="text-3xl font-semibold mb-2">{dailyDD.toFixed(2)}%</p>
            <div>
              <span className={`text-xs px-2 py-1 rounded ${dailyDD >= Number(maxDailyLimitPct) ? 'bg-[#ff4b4b]/10 text-[#ff4b4b]' : 'text-[#00cc96] bg-[#00cc96]/10'}`}>
                {dailyDD >= Number(maxDailyLimitPct) ? 'Breached' : 'Safe'} • limit {maxDailyLimitPct}%
              </span>
            </div>
          </div>
          <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-5 text-center flex flex-col justify-center">
            <p className="text-sm text-gray-400 mb-2">Max trailing drawdown</p>
            <p className="text-3xl font-semibold mb-2">{maxDD.toFixed(2)}%</p>
            <div>
              <span className={`text-xs px-2 py-1 rounded ${maxDD >= Number(maxTrailingLimitPct) ? 'bg-[#ff4b4b]/10 text-[#ff4b4b]' : 'text-[#00cc96] bg-[#00cc96]/10'}`}>
                {maxDD >= Number(maxTrailingLimitPct) ? 'Breached' : 'Safe'} • limit {maxTrailingLimitPct}%
              </span>
            </div>
          </div>
          <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-5 flex flex-col justify-center">
            <p className="text-sm text-gray-400 mb-2">Account balance</p>
            <p className="text-2xl font-semibold mb-2">${balance.toLocaleString(undefined, {minimumFractionDigits: 2})}</p>
            <p className="text-xs text-[#00cc96]">↗ +{sod ? (((balance / sod) - 1) * 100).toFixed(2) : 0}% today</p>
          </div>
          <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-5 flex flex-col justify-center">
            <p className="text-sm text-gray-400 mb-2">Equity & Margin</p>
            <p className="text-2xl font-semibold mb-2">${equity.toLocaleString(undefined, {minimumFractionDigits: 2})}</p>
            <div className="flex justify-between w-full mt-1">
              <p className="text-xs text-gray-400">Level: <span className={state.margin_level > 100 ? "text-[#00cc96]" : "text-[#ff4b4b]"}>{state.margin_level > 0 ? `${state.margin_level.toFixed(2)}%` : 'N/A'}</span></p>
              <p className="text-xs text-gray-400">Free: ${state.free_margin > 0 ? state.free_margin.toLocaleString(undefined, {minimumFractionDigits: 0}) : '0'}</p>
            </div>
          </div>
        </div>

        {/* Bottom Layout */}
        <div className="flex flex-col lg:grid lg:grid-cols-3 gap-4 flex-1 min-h-0">
          <div className="lg:col-span-2 bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 flex flex-col">
            <div className="flex justify-between items-center mb-4">
              <div>
                <h2 className="text-sm font-medium">Live market • {config.symbols_to_trade?.[0] || 'XAUUSD'}</h2>
                <div className="flex items-baseline gap-2 mt-1">
                  <span className="text-xl font-semibold">{chartData.length > 0 ? chartData[chartData.length-1].close.toFixed(2) : "Loading..."}</span>
                  <span className={`text-xs font-medium tracking-wide bg-[#2a2a2a] px-2 py-0.5 rounded ml-2 ${config.bot_status === 'running' ? 'text-brand text-gray-300' : 'text-gray-500'}`}>
                    {config.bot_status === 'running' ? countdownStr : 'Bot Stopped'}
                  </span>
                </div>
              </div>
              <div className="bg-[#2a2a2a] text-xs px-3 py-1.5 rounded">{config.timeframe || 15}M</div>
            </div>
            
            <div ref={chartContainerRef} className="flex-1 w-full min-h-[300px]" />
            
          </div>

          <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 flex flex-col">
            <div className="flex justify-between items-center mb-4 pb-4 border-b border-[#2a2a2a]">
              <div className="flex gap-4">
                <button 
                  onClick={() => setActiveTab('positions')}
                  className={`text-sm font-medium transition-colors ${activeTab === 'positions' ? 'text-white' : 'text-gray-500 hover:text-gray-300'}`}
                >
                  Active <span className="text-xs bg-[#2a2a2a] px-2 py-0.5 rounded-full ml-1">{positions.length}</span>
                </button>
                <button 
                  onClick={() => setActiveTab('history')}
                  className={`text-sm font-medium transition-colors ${activeTab === 'history' ? 'text-white' : 'text-gray-500 hover:text-gray-300'}`}
                >
                  History <span className="text-xs bg-[#2a2a2a] px-2 py-0.5 rounded-full ml-1">{history.length}</span>
                </button>
              </div>
            </div>
            
            <div className="flex-1 overflow-auto pr-1">
              {activeTab === 'positions' ? (
                // ACTIVE POSITIONS
                positions.length > 0 ? positions.map((p: any, i: number) => (
                  <div key={i} className="flex justify-between items-center py-3 border-b border-[#2a2a2a] last:border-0">
                    <div>
                      <div className="font-semibold text-sm mb-1">{p.symbol}</div>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${p.type === 'BUY' ? 'text-[#00cc96] bg-[#00cc96]/10' : 'text-[#ff4b4b] bg-[#ff4b4b]/10'}`}>
                        {p.type === 'BUY' ? 'Buy' : 'Sell'} {p.volume}
                      </span>
                    </div>
                    <div className="text-right">
                      <div className={`font-semibold text-sm mb-1 ${p.profit >= 0 ? 'text-[#00cc96]' : 'text-[#ff4b4b]'}`}>
                        {p.profit >= 0 ? '+' : ''}${p.profit.toFixed(2)}
                      </div>
                      <div className="text-[10px] text-gray-500">{p.price_open} → {p.price_current}</div>
                    </div>
                  </div>
                )) : (
                  <div className="text-center text-gray-500 mt-10 text-sm">No active trades right now.</div>
                )
              ) : (
                // TRADE HISTORY
                history.length > 0 ? history.slice().reverse().map((h: any, i: number) => (
                  <div key={i} className="flex justify-between items-center py-3 border-b border-[#2a2a2a] last:border-0">
                    <div>
                      <div className="font-semibold text-sm mb-1">{h.symbol}</div>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${h.type === 'BUY' ? 'text-[#00cc96] bg-[#00cc96]/10' : 'text-[#ff4b4b] bg-[#ff4b4b]/10'}`}>
                        {h.type} {h.volume}
                      </span>
                    </div>
                    <div className="text-right">
                      <div className={`font-semibold text-sm mb-1 ${h.profit >= 0 ? 'text-[#00cc96]' : 'text-[#ff4b4b]'}`}>
                        {h.profit >= 0 ? '+' : ''}${h.profit.toFixed(2)}
                      </div>
                      <div className="text-[10px] text-gray-500">{h.time}</div>
                    </div>
                  </div>
                )) : (
                  <div className="text-center text-gray-500 mt-10 text-sm">No closed trades today.</div>
                )
              )}
            </div>
            
            <div className="pt-4 mt-auto border-t border-[#2a2a2a] flex justify-between items-center">
              <span className="text-sm text-gray-400">
                {activeTab === 'positions' ? 'Total open P&L' : 'Realized today'}
              </span>
              <span className={`font-semibold ${
                (activeTab === 'positions' ? openPnl : state.daily_pnl) >= 0 ? 'text-[#00cc96]' : 'text-[#ff4b4b]'
              }`}>
                {(activeTab === 'positions' ? openPnl : state.daily_pnl) >= 0 ? '+' : ''}
                ${(activeTab === 'positions' ? openPnl : state.daily_pnl)?.toLocaleString(undefined, {minimumFractionDigits: 2})}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
