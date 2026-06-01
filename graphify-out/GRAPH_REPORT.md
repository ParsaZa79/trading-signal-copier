# Graph Report - trading-signal-copier  (2026-06-01)

## Corpus Check
- 130 files · ~71,257 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1903 nodes · 3857 edges · 109 communities (96 shown, 13 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 496 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d14ef390`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 87|Community 87]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 93|Community 93]]
- [[_COMMUNITY_Community 94|Community 94]]
- [[_COMMUNITY_Community 95|Community 95]]
- [[_COMMUNITY_Community 96|Community 96]]
- [[_COMMUNITY_Community 98|Community 98]]
- [[_COMMUNITY_Community 99|Community 99]]
- [[_COMMUNITY_Community 100|Community 100]]
- [[_COMMUNITY_Community 112|Community 112]]
- [[_COMMUNITY_Community 113|Community 113]]

## God Nodes (most connected - your core abstractions)
1. `MT5Executor` - 79 edges
2. `cn()` - 65 edges
3. `TradeSignal` - 65 edges
4. `BotGui` - 57 edges
5. `OrderType` - 55 edges
6. `TelegramMT5Bot` - 54 edges
7. `DualPosition` - 46 edges
8. `TradeRole` - 42 edges
9. `PositionStatus` - 41 edges
10. `str` - 41 edges

## Surprising Connections (you probably didn't know these)
- `TestEditRaceCondition` --uses--> `MT5Config`  [INFERRED]
  bot/tests/test_swing_trade_fixes.py → api/src/config.py
- `TestMarketOrderCompleteness` --uses--> `MT5Config`  [INFERRED]
  bot/tests/test_swing_trade_fixes.py → api/src/config.py
- `ConnectionManager` --uses--> `MT5Executor`  [INFERRED]
  api/src/websocket/broadcaster.py → bot/src/tania_signal_copier/executor.py
- `float` --uses--> `MT5Executor`  [INFERRED]
  api/src/websocket/broadcaster.py → bot/src/tania_signal_copier/executor.py
- `TestRealWorldSignalMessages` --uses--> `MT5Config`  [INFERRED]
  bot/tests/test_swing_trade_fixes.py → api/src/config.py

## Communities (109 total, 13 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.04
Nodes (29): MT5Config, MT5 connection configuration., Tests for swing trade timeout and signal completeness fixes.  These tests cover, Tests for Fix 3: Try multiple TPs and fallback to 1:1 RR when all breached., Set up executor mock for each test., For BUY, if TP1 > entry, use TP1 with no warning., For SELL, if TP1 < entry, use TP1 with no warning., For BUY, if TP1 <= entry (breached), try TP2. (+21 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (37): int, str, TradeSignal, Handle new trading signal (complete or incomplete).          Uses the configured, Complete pending dual positions with SL/TP from new complete signal.          Ar, Calculate default SL based on risk settings., Calculate default TP based on 1:RR risk-reward ratio.          Args:, Main bot that connects Telegram signals to MT5.      This class coordinates all (+29 more)

### Community 2 - "Community 2"
Cohesion: 0.09
Nodes (60): bool, DualPosition, float, OrderType, TrackedPosition, OrderType, TradeConfig, bool (+52 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (55): bool, datetime, float, int, str, build_signals(), classify_event(), contains_check_mark() (+47 more)

### Community 4 - "Community 4"
Cohesion: 0.06
Nodes (48): str, Path, delete_preset(), _ensure_presets_dir(), _format_env_value(), get_config(), get_preset(), list_presets() (+40 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (33): bool, float, int, str, BotConfig, _env_optional_float(), LLMConfig, MT5Config (+25 more)

### Community 6 - "Community 6"
Cohesion: 0.16
Nodes (13): ConnectionStatus(), ConnectionStatusProps, ModifyDialog(), ModifyDialogProps, PositionsTableProps, Position, Badge(), BadgeProps (+5 more)

### Community 7 - "Community 7"
Cohesion: 0.11
Nodes (28): AnalysisSummaryData, BotStatusType, iconTone, MetricCard(), MetricCardProps, SymbolCell(), EmptyState(), EmptyStateProps (+20 more)

### Community 8 - "Community 8"
Cohesion: 0.08
Nodes (25): bool, MT5Executor, str, Integration tests for MT5Executor reconnection functionality.  Tests the reconne, Test that operations auto-reconnect after disconnect., Test health check functionality., Test automatic reconnection via the with_reconnect decorator., Test _ensure_connected returns True when connection is good. (+17 more)

### Community 9 - "Community 9"
Cohesion: 0.08
Nodes (27): AccountCardProps, PortfolioHeroProps, useWebSocket(), UseWebSocketReturn, DashboardContext, DashboardContextType, DashboardLayout(), DashboardLayoutProps (+19 more)

### Community 10 - "Community 10"
Cohesion: 0.11
Nodes (35): ConfigSection, cancelOrder(), clearTrackedPositions(), closePosition(), deletePreset(), fetchApi(), getAccountInfo(), getAnalysisSummary() (+27 more)

### Community 11 - "Community 11"
Cohesion: 0.10
Nodes (11): Tests for Fix 2: Market orders only need SL and TP to be complete., Market BUY with SL and TP but no entry should be COMPLETE., Market SELL with SL and TP but no entry should be COMPLETE., Market order without SL should be INCOMPLETE., Market order without TP should be INCOMPLETE., BUY_LIMIT pending order REQUIRES entry price., SELL_LIMIT pending order REQUIRES entry price., BUY_STOP pending order REQUIRES entry price. (+3 more)

### Community 12 - "Community 12"
Cohesion: 0.05
Nodes (35): bool, DualPosition, int, Path, str, TrackedPosition, Tracks an open position linked to Telegram signals.      This class maintains th, Serialize to dictionary for JSON storage. (+27 more)

### Community 13 - "Community 13"
Cohesion: 0.12
Nodes (29): build_bot_command(), delete_preset(), ensure_presets_dir(), fetch_telegram_channels(), format_env_value(), list_presets(), load_cache(), load_preset() (+21 more)

### Community 14 - "Community 14"
Cohesion: 0.12
Nodes (10): BotGui, float, int, Show context menu for log view., Clear all tracked positions from bot_state.json after confirmation., ExitStatus, ProcessError, QMainWindow (+2 more)

### Community 15 - "Community 15"
Cohesion: 0.08
Nodes (26): str, int, str, LLMConfig, LLMProvider, int, str, LLMProvider (+18 more)

### Community 16 - "Community 16"
Cohesion: 0.07
Nodes (42): DashboardPage(), AccountCard(), AssetBreakdown(), AssetBreakdownProps, buildEquityCurve(), ChartPoint, EquityChart(), EquityChartProps (+34 more)

### Community 17 - "Community 17"
Cohesion: 0.07
Nodes (29): dependencies, clsx, financial-flag-icons, framer-motion, lucide-react, next, react, react-dom (+21 more)

### Community 18 - "Community 18"
Cohesion: 0.08
Nodes (15): bool, Check if connection is alive., Initialize connection to MT5 terminal., Enable/disable symbol in Market Watch., Check if connection is alive by getting terminal info., Initialize connection to MT5 Docker container., Verify MT5 connection (login handled via VNC in Docker)., Enable/disable symbol in Market Watch. (+7 more)

### Community 19 - "Community 19"
Cohesion: 0.12
Nodes (10): Any, MT5AdapterBase, Check if order can be executed before sending., Get historical rates., Get all available symbols., Abstract base class for MT5 adapters., Shutdown MT5 connection., Get account information. (+2 more)

### Community 20 - "Community 20"
Cohesion: 0.12
Nodes (10): int, Get total number of open positions., Get total number of available symbols., Get total number of available symbols., Get pending orders, optionally filtered by symbol or ticket., Get history deals within date range or for specific position., Get total number of available symbols., Get pending orders, optionally filtered by symbol or ticket. (+2 more)

### Community 21 - "Community 21"
Cohesion: 0.12
Nodes (23): bool, int, MT5Adapter, MT5Executor, str, TradeSignal, gold_symbol(), is_mt5_available() (+15 more)

### Community 22 - "Community 22"
Cohesion: 0.14
Nodes (22): BaseModel, Positions router for managing open positions., AccountInfo, A single trade history entry., Response containing trade history., TradeHistoryEntry, TradeHistoryResponse, ClosePositionResponse (+14 more)

### Community 23 - "Community 23"
Cohesion: 0.08
Nodes (23): 1) Start MT5 Docker, 2) Start API, 3) Start Dashboard, 4) Run Bot (optional, if not started via dashboard), code:bash (./start-linux.sh), code:bash (cd silicon-metatrader5/docker), code:bash (cd api), code:bash (cd dashboard) (+15 more)

### Community 24 - "Community 24"
Cohesion: 0.13
Nodes (8): InsightCard, MetricCard, Reset all metric cards to default state., Load tracked positions from bot_state.json into the table., A compact styled card displaying a metric value and label., A compact styled card for displaying an insight/tip., QFrame, QWidget

### Community 25 - "Community 25"
Cohesion: 0.12
Nodes (12): int, Get pending order details by ticket number.          Auto-reconnects if connecti, Cancel a pending order by ticket.          Auto-reconnects if connection is lost, Get historical deals from MT5.          Auto-reconnects if connection is lost., Get position details by ticket number.          Auto-reconnects if connection is, Check if position is in profit.          Auto-reconnects if connection is lost., Check if closing at current price would be profitable.          For TP verificat, Get the price at which a position would close.          Args:             symbol (+4 more)

### Community 26 - "Community 26"
Cohesion: 0.14
Nodes (21): PositionsTable(), formatDayLabel(), formatWeekLabel(), getDateFromTrade(), getDayKey(), getGroupingMode(), getWeekKey(), getWeekStart() (+13 more)

### Community 27 - "Community 27"
Cohesion: 0.10
Nodes (25): int, str, CancelOrderResponse, PendingOrderResponse, PlaceOrderRequest, PlaceOrderResponse, cancel_order(), list_pending_orders() (+17 more)

### Community 28 - "Community 28"
Cohesion: 0.17
Nodes (12): float, str, TradeSignal, Find first valid TP or calculate 1:1 RR fallback.          Iterates through TPs, Get current account balance.          Auto-reconnects if connection is lost., Get symbol information, trying common variations.          Auto-reconnects if co, Execute a trade signal on MT5.          Auto-reconnects if connection is lost., Execute dual trades for a signal based on strategy configs.          Args: (+4 more)

### Community 29 - "Community 29"
Cohesion: 0.16
Nodes (10): str, Test pending order placement and management.      WARNING: These tests place rea, Test placing a BUY_LIMIT pending order.          BUY_LIMIT: Placed below current, Test placing a SELL_LIMIT pending order.          SELL_LIMIT: Placed above curre, Test placing a BUY_STOP pending order.          BUY_STOP: Placed above current p, Test placing a SELL_STOP pending order.          SELL_STOP: Placed below current, Test retrieving a pending order by ticket., Test retrieving pending orders filtered by symbol. (+2 more)

### Community 30 - "Community 30"
Cohesion: 0.09
Nodes (19): float, int, WebSocket, ConnectionManager, _build_update_message(), Background broadcaster for real-time updates., Background task that broadcasts position and account updates.      Args:, Build the update message with positions and account info.      Args:         exe (+11 more)

### Community 31 - "Community 31"
Cohesion: 0.25
Nodes (5): Test risk calculation methods., Test default SL calculation for BUY order., Test default SL calculation for SELL order., Test SL calculation uses fallback for unknown symbol., TestMT5ExecutorRiskCalculations

### Community 32 - "Community 32"
Cohesion: 0.10
Nodes (19): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+11 more)

### Community 33 - "Community 33"
Cohesion: 0.18
Nodes (15): str, get_symbol_info(), _get_symbol_label(), get_symbol_price(), list_symbols(), PriceResponse, Symbols router for symbol information and prices., Get detailed information about a symbol.      Args:         symbol: The symbol n (+7 more)

### Community 34 - "Community 34"
Cohesion: 0.13
Nodes (15): float, MT5Executor, SimpleNamespace, MT5Executor, Get pending orders, optionally filtered by symbol.          Auto-reconnects if c, Shutdown MT5 connection., Perform a comprehensive health check of the MT5 connection.          Returns:, Handles trade execution on MetaTrader 5.      Provides high-level trading operat (+7 more)

### Community 35 - "Community 35"
Cohesion: 0.15
Nodes (10): str, Test symbol information operations., Test getting info for a valid symbol., Test symbol info contains trading-related attributes., Test that invalid symbol returns None., Test getting current tick for valid symbol., Test tick returns None for invalid symbol., Test enabling symbol in Market Watch. (+2 more)

### Community 36 - "Community 36"
Cohesion: 0.08
Nodes (35): bool, int, str, Popen, get_analysis_summary(), Analysis router for signal outcomes and reports., Run analysis scripts (fetch signals or generate report).      Uses asyncio.creat, Request body for running analysis scripts. (+27 more)

### Community 37 - "Community 37"
Cohesion: 0.09
Nodes (26): Any, Path, str, WebSocket, Set the log manager for streaming bot output., set_log_manager(), health_check(), Check MT5 connection health.      Returns:         dict: Health status including (+18 more)

### Community 38 - "Community 38"
Cohesion: 0.13
Nodes (13): ensure_single_instance(), _is_process_running(), _kill_process(), main(), Telegram to MetaTrader 5 Signal Bot ====================================  Main b, Stop the bot and cleanup resources., Start the bot and begin monitoring the Telegram channel.          Implements aut, Main loop with automatic reconnection on network failures. (+5 more)

### Community 39 - "Community 39"
Cohesion: 0.15
Nodes (9): str, Get symbol information., Get current tick for symbol., Get symbol information., Get current tick for symbol., Get open positions, optionally filtered by symbol or ticket., Get symbol information., Get current tick for symbol. (+1 more)

### Community 40 - "Community 40"
Cohesion: 0.12
Nodes (9): get_last_preset(), Populate all input fields from a values dictionary., Fetch and populate the channel dropdown from Telegram., Set the channel combo to match a value (ID or username)., Update the preset dropdown with available presets., Enable/disable preset buttons based on current selection., Handle preset dropdown selection change., Delete the currently selected preset. (+1 more)

### Community 41 - "Community 41"
Cohesion: 0.17
Nodes (13): int, ClosePositionResponse, ModifyPositionRequest, ModifyPositionResponse, PositionResponse, close_position(), get_position(), list_positions() (+5 more)

### Community 42 - "Community 42"
Cohesion: 0.12
Nodes (12): bool, int, str, WebSocket, LogManager, Manages WebSocket connections for streaming bot logs., Initialize the log manager., Accept and register a new WebSocket connection.          Sends buffered logs to (+4 more)

### Community 43 - "Community 43"
Cohesion: 0.15
Nodes (10): bool, Test MT5 connection lifecycle., Test successful initialization to Docker container., Test that initialization fails with wrong port., Test ping returns True after successful initialization., Test ping returns False before initialization., Test that shutdown clears the internal client., Test login verification (credentials already set in Docker VNC). (+2 more)

### Community 44 - "Community 44"
Cohesion: 0.20
Nodes (11): Tabs(), TabsContent(), TabsContentProps, TabsContext, TabsContextValue, TabsList(), TabsListProps, TabsProps (+3 more)

### Community 45 - "Community 45"
Cohesion: 0.17
Nodes (15): get_prompts(), _load_custom_prompts(), System prompts management router., Load custom prompts from file., Save custom prompts to file., Request body for saving system prompts., Get current system prompts.      Returns the active prompts (custom if set, othe, Save custom system prompts.      Only saves prompts that are provided (non-None) (+7 more)

### Community 46 - "Community 46"
Cohesion: 0.12
Nodes (11): ABC, main(), create_mt5_adapter(), MacOSMT5Adapter, MetaTrader 5 Adapter - Cross-Platform Support ==================================, MetaTrader 5 adapter for macOS using siliconmetatrader5 + Docker., Get last error (limited info available via Docker)., Get account information. (+3 more)

### Community 47 - "Community 47"
Cohesion: 0.13
Nodes (14): code:bash (cd bot), code:bash (cd bot), code:bash (cd bot), code:bash (cd bot), Development, GUI, Headless Bot, Important Config Keys (+6 more)

### Community 48 - "Community 48"
Cohesion: 0.13
Nodes (13): Architecture, code:bash (# Development), code:block2 (NEXT_PUBLIC_API_URL=http://localhost:8000), code:tsx (const { positions, account, isConnected, error, reconnect } ), code:block4 (src/), Commands, Directory Structure, Environment Variables (+5 more)

### Community 49 - "Community 49"
Cohesion: 0.12
Nodes (10): bool, Test execution auto-reconnects when not initially connected., Test position modification and closure.      WARNING: These tests may place real, Test modify auto-reconnects when not initially connected., Test modify fails with invalid ticket., Test close auto-reconnects when not initially connected., Test close fails with invalid ticket., Test complete trade lifecycle: open -> modify -> close.          WARNING: This t (+2 more)

### Community 50 - "Community 50"
Cohesion: 0.14
Nodes (8): Test symbol lookup tries variations., Test invalid symbol returns None., Test getting bid price., Test getting ask price., Test that spread (ask - bid) is positive., Test symbol-related operations., Test getting info for valid symbol., TestMT5ExecutorSymbolOperations

### Community 51 - "Community 51"
Cohesion: 0.21
Nodes (12): datetime, float, int, str, add_trade(), get_trade_history(), get_trade_stats(), Trade history service using SQLite. (+4 more)

### Community 52 - "Community 52"
Cohesion: 0.14
Nodes (9): Tests for the signal bot., Test creating a trade signal., Test all order types are valid., Tests for SignalParser class., Test parsing a valid trading signal., Test that invalid messages return None., Tests for TradeSignal dataclass., TestSignalParser (+1 more)

### Community 53 - "Community 53"
Cohesion: 0.15
Nodes (12): code:bash (cd api), code:bash (cd api), code:bash (cd api), Development, Environment Variables, Main Endpoints, Persistence (Dokploy), Requirements (+4 more)

### Community 54 - "Community 54"
Cohesion: 0.15
Nodes (11): Architecture, code:bash (# Install dependencies), code:bash (colima start --arch x86_64 --vm-type=qemu --cpu 4 --memory 8), code:bash (docker run -d --name mt5 -p 3000:3000 -p 8001:8001 gmag11/me), Core Components (src/tania_signal_copier/), Data Flow, Development Commands, Key Dependencies (+3 more)

### Community 55 - "Community 55"
Cohesion: 0.16
Nodes (18): AccountInfo, int, str, bool, str, get_account_info(), get_trade_history(), Account router for account info and trade history. (+10 more)

### Community 56 - "Community 56"
Cohesion: 0.33
Nodes (3): Check if order can be executed before sending., Check if order can be executed before sending., Check if order can be executed before sending.

### Community 57 - "Community 57"
Cohesion: 0.20
Nodes (11): float, int, Namespace, fetch_messages(), parse_args(), print_summary(), Save messages to JSON file., Print summary of fetched messages. (+3 more)

### Community 58 - "Community 58"
Cohesion: 0.09
Nodes (32): bool, float, LLMConfig, str, TradeSignal, Test position query methods., Test account-related operations., TestMT5ExecutorAccountOperations (+24 more)

### Community 59 - "Community 59"
Cohesion: 0.33
Nodes (4): dmSans, inter, jetbrainsMono, metadata

### Community 60 - "Community 60"
Cohesion: 0.18
Nodes (9): Architecture, code:bash (# Install dependencies (uses uv)), Commands, Configuration, Data Flow, Database, Key Components, Module Loading Strategy (+1 more)

### Community 61 - "Community 61"
Cohesion: 0.18
Nodes (10): API Integration, Available Scripts, code:bash (cd dashboard), code:bash (cd dashboard), code:dotenv (NEXT_PUBLIC_API_URL=http://localhost:8000), Environment, Requirements, Run (Development) (+2 more)

### Community 62 - "Community 62"
Cohesion: 0.22
Nodes (6): bool, Initialize and connect to MT5.          Returns:             True if connection, Get current ask (for buy) or bid (for sell) price.          Auto-reconnects if c, Check if the connection to MT5 is alive.          Performs a ping to verify the, Ensure we have an active connection, checking periodically.          Returns:, Attempt to reconnect to MT5 with retries.          Returns:             True if

### Community 63 - "Community 63"
Cohesion: 0.24
Nodes (7): MT5Adapter, Test account information retrieval., Test that account_info returns account object., Test account_info contains expected attributes., Test that balance is a valid number., Test account_info returns None without connection., TestMT5AdapterAccountInfo

### Community 64 - "Community 64"
Cohesion: 0.25
Nodes (10): analyze_signals(), generate_report(), load_raw_signals(), print_summary(), Save parsed results to JSON., Generate markdown analysis report., Print summary statistics., Load raw signals from JSON file. (+2 more)

### Community 65 - "Community 65"
Cohesion: 0.12
Nodes (11): LinuxMT5Adapter, Shutdown MT5 connection., Shutdown MT5 connection., MetaTrader 5 adapter for Linux using rpyc + Docker (gmag11/metatrader5_vnc)., Evaluate a Python expression on the remote MT5 server., Verify MT5 connection (login handled via VNC in Docker)., Shutdown MT5 connection., Get last error from MT5. (+3 more)

### Community 66 - "Community 66"
Cohesion: 0.20
Nodes (6): Test signal execution (actually places orders).      WARNING: These tests place, Test execution fails with invalid symbol., Test executing a BUY market order.          WARNING: This test places a real ord, Test executing a SELL market order.          WARNING: This test places a real or, Test executing order with SL and TP.          WARNING: This test places a real o, TestMT5ExecutorSignalExecution

### Community 67 - "Community 67"
Cohesion: 0.20
Nodes (6): Test position retrieval operations., Test positions_total returns an integer., Test positions_get returns a list., Test positions_get with non-existent ticket returns empty list., Test positions_get with invalid symbol returns empty list., TestMT5AdapterPositions

### Community 68 - "Community 68"
Cohesion: 0.33
Nodes (4): Integration tests for MT5Adapter.  Tests the low-level MT5 interface against a r, Test error retrieval., Test last_error returns a tuple., TestMT5AdapterLastError

### Community 69 - "Community 69"
Cohesion: 0.31
Nodes (5): pageTransition, pageVariants, staggerContainer, staggerItem, AnimatedSectionProps

### Community 70 - "Community 70"
Cohesion: 0.31
Nodes (8): str, get_message_type_color(), main(), parse_log_file(), Test script to verify Claude signal parsing on logged messages.  Tests all 7 mes, Parse telegram_messages.log into individual messages., Get ANSI color code for message type., Test signal parsing on logged messages.

### Community 71 - "Community 71"
Cohesion: 0.22
Nodes (7): Config, eslintConfig, mt5_credentials(), pytest_configure(), Root conftest.py for tania-signal-copier tests.  Contains shared fixtures and co, Register custom markers., Provide MT5 credentials from environment variables.      Returns:         dict w

### Community 72 - "Community 72"
Cohesion: 0.15
Nodes (13): SymbolListItem, ORDER_TYPES, PENDING_ORDER_TYPES, SYMBOLS, OrderForm(), OrderFormProps, OrderType, PlaceOrderRequest (+5 more)

### Community 73 - "Community 73"
Cohesion: 0.21
Nodes (11): FallbackSymbolIcon(), getFallbackMeta(), getSymbolMeta(), sizeStyles, SymbolCellProps, SymbolIcon(), SymbolIconProps, SymbolMeta (+3 more)

### Community 74 - "Community 74"
Cohesion: 0.25
Nodes (5): Test MT5 constants are properly defined., Test trade action constants., Test order type constants., Test other trading constants., TestMT5AdapterConstants

### Community 75 - "Community 75"
Cohesion: 0.20
Nodes (13): CRYPTO_COINS, CURRENCY_TO_FLAG, FINANCIAL_FLAG_KEYS, FOREX_CURRENCIES, INDEX_LOGO_RULES, resolveCommodity(), resolveCrypto(), ResolvedSymbolIcon (+5 more)

### Community 76 - "Community 76"
Cohesion: 0.22
Nodes (5): MT5Executor, Test getting non-existent position returns None., Test profitability check for non-existent position., Test getting account balance., Test cancelling a non-existent order returns error.

### Community 79 - "Community 79"
Cohesion: 0.33
Nodes (3): Get historical rates., Get historical rates (use position-based for fresh data)., Get historical rates.

### Community 80 - "Community 80"
Cohesion: 0.20
Nodes (6): Integration tests for MT5Executor.  Tests the high-level trading executor agains, Test MT5Executor connection management., Test successful connection., Test disconnection sets connected to False., Test that connect creates internal MT5 adapter., TestMT5ExecutorConnection

### Community 81 - "Community 81"
Cohesion: 0.60
Nodes (4): main(), Test a single message and return results., test_message(), SignalParser

### Community 82 - "Community 82"
Cohesion: 0.22
Nodes (7): int, str, FastAPI, get_telegram_channels(), Telegram channels router., Get list of available Telegram channels/groups.      Requires api_id and api_has, WebSocket log streaming manager for bot output.

### Community 83 - "Community 83"
Cohesion: 0.60
Nodes (3): check_command(), wait_for_port(), start-linux.sh script

### Community 85 - "Community 85"
Cohesion: 0.50
Nodes (3): MT5 trade executor for the Telegram Signal Bot.  This module handles all MetaTra, Decorator that ensures connection before executing a method.      If connection, with_reconnect()

### Community 86 - "Community 86"
Cohesion: 0.50
Nodes (3): main(), Test script to fetch last 10 messages from the configured Telegram channel.  Usa, Fetch and display last 10 messages from the channel.

### Community 87 - "Community 87"
Cohesion: 1.00
Nodes (3): apply_app_style(), main(), QApplication

### Community 112 - "Community 112"
Cohesion: 0.33
Nodes (4): Test historical data retrieval., Test getting historical candle data., Test copy_rates with invalid symbol., TestMT5AdapterHistoricalData

### Community 113 - "Community 113"
Cohesion: 0.14
Nodes (8): MetaTrader 5 adapter for Windows using native MetaTrader5 package., Initialize Windows MT5 adapter.          Args:             path: Path to MT5 ter, Login to MT5 account.          On Windows, this actually performs authentication, Get last error from MT5., Get account information., Get total number of open positions., Get all available symbols., WindowsMT5Adapter

## Knowledge Gaps
- **212 isolated node(s):** `config`, `name`, `version`, `private`, `dev` (+207 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MT5Executor` connect `Community 34` to `Community 0`, `Community 1`, `Community 2`, `Community 8`, `Community 11`, `Community 21`, `Community 25`, `Community 28`, `Community 29`, `Community 30`, `Community 31`, `Community 49`, `Community 50`, `Community 58`, `Community 62`, `Community 66`, `Community 76`, `Community 80`, `Community 85`?**
  _High betweenness centrality (0.145) - this node is a cross-community bridge._
- **Why does `create_mt5_adapter()` connect `Community 46` to `Community 65`, `Community 39`, `Community 43`, `Community 113`, `Community 19`, `Community 20`, `Community 62`?**
  _High betweenness centrality (0.076) - this node is a cross-community bridge._
- **Why does `SignalParser` connect `Community 58` to `Community 0`, `Community 1`, `Community 2`, `Community 11`, `Community 81`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Are the 49 inferred relationships involving `MT5Executor` (e.g. with `float` and `bool`) actually correct?**
  _`MT5Executor` has 49 INFERRED edges - model-reasoned connections that need verification._
- **Are the 62 inferred relationships involving `TradeSignal` (e.g. with `bool` and `DualPosition`) actually correct?**
  _`TradeSignal` has 62 INFERRED edges - model-reasoned connections that need verification._
- **Are the 51 inferred relationships involving `OrderType` (e.g. with `bool` and `DualPosition`) actually correct?**
  _`OrderType` has 51 INFERRED edges - model-reasoned connections that need verification._
- **What connects `config`, `name`, `version` to the rest of the system?**
  _809 weakly-connected nodes found - possible documentation gaps or missing edges._