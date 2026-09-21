"use client";

import { useEffect, useState, useRef } from "react";
import axios from "axios";
import { LayoutDashboard, List, Clock, Gauge, Settings, Shield, MoreVertical, CircleDot } from "lucide-react";
import { createChart, IChartApi, ISeriesApi, CandlestickData, Time, ColorType } from "lightweight-charts";

export default function Home() {
  const [state, setState] = useState<any>(null);
  const [chartData, setChartData] = useState<any[]>([]);
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [countdownStr, setCountdownStr] = useState<string>("");

  useEffect(() => {
    // Fetch State
    const fetchState = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || '/api';
        const res = await axios.get(`${apiUrl}/state`);
        setState(res.data);
      } catch (err) {
        console.error("Error fetching state", err);
      }
    };
    
    fetchState();
    const interval = setInterval(fetchState, 3000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    // Update Countdown Timer
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

  useEffect(() => {
    // Fetch Chart Data
    const fetchChart = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || '/api';
        const res = await axios.get(`${apiUrl}/chart?symbol=XAUUSD&timeframe=15&count=200`);
        setChartData(res.data.data);
      } catch (err) {
        console.error("Error fetching chart data", err);
      }
    };
    fetchChart();
  }, []);

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

  if (!state) {
    return <div className="min-h-screen bg-[#121212] flex items-center justify-center text-white">Connecting to FastAPI Engine...</div>;
  }

  const balance = state.balance || 0;
  const equity = state.equity || 0;
  const sod = state.start_of_day_balance || balance;
  const dailyDD = sod > 0 ? Math.max(0, ((sod - equity) / sod) * 100) : 0;
  const hw = state.highest_equity || equity;
  const maxDD = hw > 0 ? Math.max(0, ((hw - equity) / hw) * 100) : 0;

  const positions = state.positions || [];
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
            <h1 className="text-xl font-semibold">Risk management</h1>
            <p className="text-sm text-gray-400 mt-1">Challenge account • #482910 • ${sod.toLocaleString(undefined, {minimumFractionDigits: 0})}</p>
          </div>
          <div className="flex items-center gap-3 w-full md:w-auto">
            <span className="flex items-center gap-1.5 text-xs text-[#00cc96] bg-[#00cc96]/10 px-3 py-1.5 rounded-md font-medium">
              <CircleDot size={12} fill="currentColor" /> Live
            </span>
            <button className="flex-1 md:flex-none text-sm px-4 py-2 bg-[#2a2a2a] hover:bg-[#3a3a3a] rounded-lg border border-[#3a3a3a] transition-colors">Deploy strategy</button>
            <button className="p-2 text-gray-400 hover:text-white shrink-0"><MoreVertical size={18} /></button>
          </div>
        </div>

        {/* Top 4 Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-5 text-center flex flex-col justify-center">
            <p className="text-sm text-gray-400 mb-2">Daily loss limit</p>
            <p className="text-3xl font-semibold mb-2">{dailyDD.toFixed(2)}%</p>
            <div><span className="text-xs text-[#00cc96] bg-[#00cc96]/10 px-2 py-1 rounded">Safe • limit 5%</span></div>
          </div>
          <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-5 text-center flex flex-col justify-center">
            <p className="text-sm text-gray-400 mb-2">Max trailing drawdown</p>
            <p className="text-3xl font-semibold mb-2">{maxDD.toFixed(2)}%</p>
            <div><span className="text-xs text-[#00cc96] bg-[#00cc96]/10 px-2 py-1 rounded">Safe • limit 10%</span></div>
          </div>
          <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-5 flex flex-col justify-center">
            <p className="text-sm text-gray-400 mb-2">Account balance</p>
            <p className="text-2xl font-semibold mb-2">${balance.toLocaleString(undefined, {minimumFractionDigits: 2})}</p>
            <p className="text-xs text-[#00cc96]">↗ +{sod ? (((balance / sod) - 1) * 100).toFixed(2) : 0}% today</p>
          </div>
          <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-5 flex flex-col justify-center">
            <p className="text-sm text-gray-400 mb-2">Equity</p>
            <p className="text-2xl font-semibold mb-2">${equity.toLocaleString(undefined, {minimumFractionDigits: 2})}</p>
            <p className="text-xs text-gray-400">Open P&L <span className={openPnl >= 0 ? "text-[#00cc96]" : "text-[#ff4b4b]"}>{openPnl >= 0 ? "+" : ""}${openPnl.toLocaleString(undefined, {minimumFractionDigits: 2})}</span></p>
          </div>
        </div>

        {/* Bottom Layout */}
        <div className="flex flex-col lg:grid lg:grid-cols-3 gap-4 flex-1 min-h-0">
          <div className="lg:col-span-2 bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 flex flex-col">
            <div className="flex justify-between items-center mb-4">
              <div>
                <h2 className="text-sm font-medium">Live market • XAUUSD</h2>
                <div className="flex items-baseline gap-2 mt-1">
                  <span className="text-xl font-semibold">{chartData.length > 0 ? chartData[chartData.length-1].close.toFixed(2) : "Loading..."}</span>
                  <span className="text-xs text-brand font-medium tracking-wide bg-[#2a2a2a] px-2 py-0.5 rounded text-gray-300 ml-2">{countdownStr}</span>
                </div>
              </div>
              <div className="bg-[#2a2a2a] text-xs px-3 py-1.5 rounded">15M</div>
            </div>
            
            <div ref={chartContainerRef} className="flex-1 w-full min-h-[300px]" />
            
          </div>

          <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-4 flex flex-col">
            <div className="flex justify-between items-center mb-4 pb-4 border-b border-[#2a2a2a]">
              <h2 className="text-sm font-medium">Active positions</h2>
              <span className="text-xs text-gray-400 bg-[#2a2a2a] px-2 py-1 rounded-full">{positions.length} open</span>
            </div>
            
            <div className="flex-1 overflow-auto">
              {positions.length > 0 ? positions.map((p: any, i: number) => (
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
              )}
            </div>
            
            <div className="pt-4 mt-auto border-t border-[#2a2a2a] flex justify-between items-center">
              <span className="text-sm text-gray-400">Total open P&L</span>
              <span className={`font-semibold ${openPnl >= 0 ? 'text-[#00cc96]' : 'text-[#ff4b4b]'}`}>
                {openPnl >= 0 ? '+' : ''}${openPnl.toLocaleString(undefined, {minimumFractionDigits: 2})}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
