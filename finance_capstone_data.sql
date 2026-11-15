INSERT INTO portfolios 
(portfolio_id, portfolio_name, portfolio_manager, risk_category, total_value, benchmark_index)
VALUES (1, 'Global Growth Portfolio 1', 'Ravi Patel', 'Low', 24865172, 'NASDAQ 100');
INSERT INTO portfolios 
(portfolio_id, portfolio_name, portfolio_manager, risk_category, total_value, benchmark_index)
VALUES (2, 'Global Growth Portfolio 2', 'Emma Wilson', 'Low', 30208844, 'S&P 500');
INSERT INTO portfolios 
(portfolio_id, portfolio_name, portfolio_manager, risk_category, total_value, benchmark_index)
VALUES (3, 'Global Growth Portfolio 3', 'Emma Wilson', 'Moderate', 44427273, 'MSCI World');
INSERT INTO portfolios 
(portfolio_id, portfolio_name, portfolio_manager, risk_category, total_value, benchmark_index)
VALUES (4, 'Global Growth Portfolio 4', 'Daniel Kim', 'Moderate', 47725279, 'MSCI World');
INSERT INTO portfolios 
(portfolio_id, portfolio_name, portfolio_manager, risk_category, total_value, benchmark_index)
VALUES (5, 'Global Growth Portfolio 5', 'Emma Wilson', 'Low', 41270417, 'NASDAQ 100');
INSERT INTO portfolios 
(portfolio_id, portfolio_name, portfolio_manager, risk_category, total_value, benchmark_index)
VALUES (6, 'Global Growth Portfolio 6', 'Daniel Kim', 'High', 31110477, 'FTSE 100');
INSERT INTO portfolios 
(portfolio_id, portfolio_name, portfolio_manager, risk_category, total_value, benchmark_index)
VALUES (7, 'Global Growth Portfolio 7', 'Emma Wilson', 'High', 46444047, 'FTSE 100');
INSERT INTO portfolios 
(portfolio_id, portfolio_name, portfolio_manager, risk_category, total_value, benchmark_index)
VALUES (8, 'Global Growth Portfolio 8', 'Alice Morgan', 'High', 12334269, 'NASDAQ 100');
INSERT INTO portfolios 
(portfolio_id, portfolio_name, portfolio_manager, risk_category, total_value, benchmark_index)
VALUES (9, 'Global Growth Portfolio 9', 'David Chen', 'Moderate', 25337066, 'FTSE 100');
INSERT INTO portfolios 
(portfolio_id, portfolio_name, portfolio_manager, risk_category, total_value, benchmark_index)
VALUES (10, 'Global Growth Portfolio 10', 'Alice Morgan', 'Low', 20252263, 'S&P 500');
INSERT INTO portfolios 
(portfolio_id, portfolio_name, portfolio_manager, risk_category, total_value, benchmark_index)
VALUES (11, 'Global Growth Portfolio 11', 'Daniel Kim', 'High', 19249968, 'S&P 500');
INSERT INTO portfolios 
(portfolio_id, portfolio_name, portfolio_manager, risk_category, total_value, benchmark_index)
VALUES (12, 'Global Growth Portfolio 12', 'Daniel Kim', 'Low', 19197473, 'NASDAQ 100');
INSERT INTO portfolios 
(portfolio_id, portfolio_name, portfolio_manager, risk_category, total_value, benchmark_index)
VALUES (13, 'Global Growth Portfolio 13', 'Sophia Martinez', 'High', 18008609, 'S&P 500');
INSERT INTO portfolios 
(portfolio_id, portfolio_name, portfolio_manager, risk_category, total_value, benchmark_index)
VALUES (14, 'Global Growth Portfolio 14', 'Ravi Patel', 'High', 37398257, 'S&P 500');
INSERT INTO portfolios 
(portfolio_id, portfolio_name, portfolio_manager, risk_category, total_value, benchmark_index)
VALUES (15, 'Global Growth Portfolio 15', 'Sophia Martinez', 'High', 12170785, 'MSCI World');
INSERT INTO portfolios 
(portfolio_id, portfolio_name, portfolio_manager, risk_category, total_value, benchmark_index)
VALUES (16, 'Global Growth Portfolio 16', 'Sophia Martinez', 'Moderate', 21611225, 'MSCI World');
INSERT INTO portfolios 
(portfolio_id, portfolio_name, portfolio_manager, risk_category, total_value, benchmark_index)
VALUES (17, 'Global Growth Portfolio 17', 'David Chen', 'Low', 14662814, 'S&P 500');
INSERT INTO portfolios 
(portfolio_id, portfolio_name, portfolio_manager, risk_category, total_value, benchmark_index)
VALUES (18, 'Global Growth Portfolio 18', 'Emma Wilson', 'Moderate', 47951662, 'FTSE 100');
INSERT INTO portfolios 
(portfolio_id, portfolio_name, portfolio_manager, risk_category, total_value, benchmark_index)
VALUES (19, 'Global Growth Portfolio 19', 'Ravi Patel', 'Moderate', 32811133, 'MSCI World');
INSERT INTO portfolios 
(portfolio_id, portfolio_name, portfolio_manager, risk_category, total_value, benchmark_index)
VALUES (20, 'Global Growth Portfolio 20', 'Daniel Kim', 'Low', 38455644, 'NASDAQ 100');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (1, 20, 'Amazon', 'Bond', 'Consumer', 14.85, 2203762, '2024-03-18');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (2, 5, 'Tesla', 'Bond', 'Energy', 2.75, 4215291, '2024-12-26');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (3, 1, 'JPMorgan', 'Equity', 'Consumer', 24.75, 1512619, '2024-10-25');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (4, 16, 'Gold ETF', 'Bond', 'Finance', 19.05, 3539382, '2024-10-04');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (5, 16, 'JPMorgan', 'Commodity', 'Finance', 4.01, 1597737, '2024-12-29');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (6, 1, 'Google', 'Bond', 'Consumer', 21.71, 1671773, '2025-01-15');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (7, 4, 'Apple Inc', 'ETF', 'Consumer', 15.92, 868095, '2024-11-29');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (8, 19, 'Nvidia', 'Commodity', 'Technology', 10.85, 3958953, '2024-08-19');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (9, 10, 'Gold ETF', 'Bond', 'Consumer', 7.45, 3227242, '2024-02-22');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (10, 17, 'Oil Futures', 'Bond', 'Consumer', 23.94, 3673723, '2024-10-17');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (11, 2, 'Apple Inc', 'ETF', 'Healthcare', 19.87, 3064366, '2025-01-10');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (12, 11, 'Oil Futures', 'Commodity', 'Finance', 15.65, 2906301, '2024-05-16');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (13, 17, 'Oil Futures', 'ETF', 'Technology', 11.1, 4436189, '2024-07-07');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (14, 15, 'Microsoft', 'Equity', 'Technology', 15.67, 3342026, '2024-07-06');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (15, 19, 'Gold ETF', 'Commodity', 'Healthcare', 20.11, 957695, '2024-04-27');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (16, 11, 'Tesla', 'Bond', 'Energy', 4.15, 2064773, '2024-05-30');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (17, 8, 'US Treasury Bonds', 'ETF', 'Energy', 12.63, 4815768, '2024-02-02');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (18, 16, 'Google', 'Commodity', 'Technology', 12.12, 138372, '2024-05-22');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (19, 14, 'Oil Futures', 'Commodity', 'Technology', 11.88, 765946, '2024-07-08');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (20, 9, 'Google', 'Equity', 'Healthcare', 22.0, 1865497, '2024-12-30');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (21, 12, 'Google', 'Commodity', 'Consumer', 16.86, 1762290, '2024-09-25');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (22, 16, 'Oil Futures', 'Bond', 'Healthcare', 16.27, 4936435, '2025-01-24');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (23, 20, 'Nvidia', 'Equity', 'Energy', 5.85, 216870, '2024-11-08');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (24, 9, 'Nvidia', 'Commodity', 'Technology', 14.74, 3301851, '2024-01-30');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (25, 15, 'Microsoft', 'Commodity', 'Healthcare', 18.26, 735458, '2024-04-03');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (26, 2, 'Gold ETF', 'Bond', 'Healthcare', 2.64, 4601634, '2024-11-07');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (27, 15, 'US Treasury Bonds', 'Bond', 'Energy', 3.78, 3946354, '2024-09-22');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (28, 13, 'Google', 'Bond', 'Finance', 20.74, 2988270, '2024-08-05');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (29, 15, 'Oil Futures', 'ETF', 'Healthcare', 24.13, 864615, '2024-10-20');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (30, 4, 'Nvidia', 'ETF', 'Technology', 24.28, 2586944, '2024-07-08');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (31, 15, 'Google', 'Equity', 'Technology', 8.83, 1466143, '2024-01-29');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (32, 5, 'Nvidia', 'Equity', 'Technology', 17.99, 4069151, '2024-07-30');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (33, 12, 'JPMorgan', 'Commodity', 'Finance', 16.71, 4216222, '2024-11-14');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (34, 17, 'Microsoft', 'Commodity', 'Energy', 12.59, 67703, '2024-03-13');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (35, 8, 'Gold ETF', 'Commodity', 'Technology', 5.45, 2876212, '2024-10-30');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (36, 13, 'Gold ETF', 'Bond', 'Healthcare', 20.68, 1831065, '2024-09-22');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (37, 12, 'US Treasury Bonds', 'ETF', 'Consumer', 6.47, 2968817, '2025-01-20');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (38, 18, 'Microsoft', 'Commodity', 'Technology', 14.03, 531376, '2024-12-14');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (39, 13, 'Google', 'Commodity', 'Technology', 23.59, 3520772, '2024-11-08');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (40, 4, 'Microsoft', 'Bond', 'Energy', 14.55, 3146181, '2025-01-09');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (41, 9, 'Oil Futures', 'Bond', 'Energy', 18.63, 3479917, '2024-04-27');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (42, 18, 'Apple Inc', 'Bond', 'Consumer', 6.48, 625820, '2024-06-12');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (43, 1, 'Oil Futures', 'Equity', 'Energy', 7.77, 1066529, '2024-07-22');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (44, 9, 'JPMorgan', 'Bond', 'Energy', 11.99, 4695379, '2024-06-14');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (45, 4, 'Microsoft', 'Equity', 'Finance', 12.3, 3240630, '2024-05-31');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (46, 7, 'Amazon', 'Commodity', 'Technology', 8.43, 2349600, '2024-12-24');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (47, 5, 'US Treasury Bonds', 'Commodity', 'Energy', 23.45, 2762385, '2024-11-03');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (48, 19, 'US Treasury Bonds', 'Bond', 'Healthcare', 10.66, 1825998, '2025-01-30');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (49, 2, 'Microsoft', 'Bond', 'Technology', 4.39, 3409710, '2024-11-05');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (50, 7, 'Tesla', 'ETF', 'Energy', 18.29, 4525107, '2024-06-05');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (51, 7, 'Amazon', 'Commodity', 'Technology', 3.3, 2502068, '2025-01-03');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (52, 10, 'Microsoft', 'Commodity', 'Consumer', 4.58, 2420484, '2024-11-02');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (53, 4, 'Oil Futures', 'Bond', 'Consumer', 17.29, 392507, '2025-02-01');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (54, 19, 'Amazon', 'Bond', 'Consumer', 20.74, 534144, '2025-01-07');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (55, 20, 'Oil Futures', 'Commodity', 'Consumer', 2.23, 4667145, '2025-02-13');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (56, 7, 'Gold ETF', 'Commodity', 'Consumer', 23.46, 614154, '2024-12-03');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (57, 18, 'JPMorgan', 'Bond', 'Technology', 22.55, 3574582, '2024-06-29');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (58, 6, 'Nvidia', 'Commodity', 'Healthcare', 21.05, 687471, '2024-12-16');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (59, 9, 'Nvidia', 'ETF', 'Healthcare', 11.98, 542697, '2025-02-10');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (60, 5, 'Google', 'Bond', 'Healthcare', 4.48, 1206485, '2024-02-23');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (61, 4, 'Gold ETF', 'Equity', 'Energy', 17.92, 1769398, '2024-08-13');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (62, 12, 'US Treasury Bonds', 'Commodity', 'Energy', 20.41, 4002268, '2024-06-29');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (63, 11, 'Nvidia', 'Bond', 'Finance', 2.14, 3792749, '2025-01-23');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (64, 13, 'Oil Futures', 'Bond', 'Energy', 3.29, 4508488, '2025-01-21');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (65, 8, 'Tesla', 'Equity', 'Technology', 23.44, 2367986, '2024-08-18');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (66, 8, 'Nvidia', 'ETF', 'Finance', 5.1, 4505087, '2024-03-25');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (67, 19, 'Amazon', 'Bond', 'Finance', 14.27, 3264291, '2024-04-17');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (68, 8, 'Apple Inc', 'Equity', 'Finance', 13.55, 3785542, '2024-04-17');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (69, 20, 'Nvidia', 'ETF', 'Energy', 9.56, 621114, '2024-03-20');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (70, 4, 'Gold ETF', 'Equity', 'Energy', 6.94, 2244072, '2024-01-01');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (71, 9, 'JPMorgan', 'Bond', 'Finance', 20.42, 1806268, '2024-06-28');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (72, 5, 'JPMorgan', 'Commodity', 'Technology', 4.62, 2717133, '2024-01-26');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (73, 8, 'Amazon', 'ETF', 'Healthcare', 20.23, 1683367, '2025-01-18');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (74, 19, 'Gold ETF', 'Bond', 'Energy', 11.17, 456812, '2025-01-08');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (75, 19, 'US Treasury Bonds', 'Equity', 'Finance', 1.74, 2186711, '2024-06-17');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (76, 14, 'Google', 'ETF', 'Healthcare', 7.1, 4159250, '2024-08-31');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (77, 11, 'JPMorgan', 'ETF', 'Technology', 20.55, 798067, '2024-06-22');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (78, 12, 'US Treasury Bonds', 'Bond', 'Energy', 21.26, 3760053, '2025-02-03');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (79, 14, 'JPMorgan', 'Equity', 'Energy', 9.81, 745222, '2024-08-10');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (80, 5, 'Microsoft', 'Bond', 'Consumer', 17.2, 4323702, '2024-05-16');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (81, 12, 'Gold ETF', 'Equity', 'Energy', 3.72, 888600, '2024-03-14');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (82, 7, 'Microsoft', 'ETF', 'Technology', 23.46, 829756, '2024-03-15');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (83, 2, 'Google', 'Commodity', 'Consumer', 23.76, 3739863, '2024-05-16');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (84, 8, 'Microsoft', 'Equity', 'Consumer', 3.06, 2165555, '2024-08-16');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (85, 8, 'JPMorgan', 'Commodity', 'Energy', 16.94, 3143806, '2024-04-30');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (86, 13, 'Microsoft', 'ETF', 'Consumer', 5.98, 1627233, '2024-06-24');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (87, 8, 'Oil Futures', 'Equity', 'Finance', 22.06, 1092997, '2024-05-05');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (88, 20, 'Apple Inc', 'Bond', 'Consumer', 10.76, 448090, '2024-08-20');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (89, 19, 'Tesla', 'Commodity', 'Energy', 6.32, 3906962, '2024-06-18');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (90, 12, 'Google', 'ETF', 'Energy', 11.27, 4223575, '2024-10-27');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (91, 11, 'Gold ETF', 'Bond', 'Finance', 5.23, 4671324, '2024-07-18');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (92, 16, 'JPMorgan', 'Equity', 'Healthcare', 2.05, 2743065, '2024-06-19');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (93, 13, 'US Treasury Bonds', 'Commodity', 'Technology', 17.1, 1769909, '2024-05-30');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (94, 10, 'Tesla', 'ETF', 'Finance', 5.92, 2548787, '2024-12-24');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (95, 11, 'Oil Futures', 'ETF', 'Energy', 16.58, 2037144, '2024-06-07');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (96, 12, 'Oil Futures', 'Bond', 'Energy', 10.04, 3967811, '2025-01-17');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (97, 7, 'US Treasury Bonds', 'Commodity', 'Healthcare', 23.35, 4632256, '2024-03-23');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (98, 11, 'Amazon', 'ETF', 'Healthcare', 24.53, 1748303, '2024-07-27');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (99, 2, 'Oil Futures', 'Bond', 'Technology', 2.7, 3648999, '2025-02-07');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (100, 12, 'Oil Futures', 'Equity', 'Energy', 3.7, 3379670, '2024-11-05');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (101, 17, 'Amazon', 'Commodity', 'Technology', 20.74, 3096725, '2024-10-13');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (102, 15, 'Google', 'Equity', 'Energy', 13.14, 349097, '2024-12-01');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (103, 4, 'US Treasury Bonds', 'Bond', 'Energy', 23.7, 4357778, '2024-11-03');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (104, 13, 'Tesla', 'Commodity', 'Healthcare', 14.33, 528750, '2024-06-30');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (105, 11, 'US Treasury Bonds', 'Bond', 'Healthcare', 23.3, 1028712, '2024-09-13');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (106, 6, 'Google', 'Bond', 'Healthcare', 1.04, 2276241, '2024-01-23');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (107, 14, 'US Treasury Bonds', 'Equity', 'Healthcare', 13.44, 3185034, '2025-01-14');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (108, 1, 'US Treasury Bonds', 'Equity', 'Energy', 22.04, 1821454, '2025-02-13');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (109, 2, 'Microsoft', 'ETF', 'Finance', 15.58, 2903887, '2024-08-05');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (110, 14, 'JPMorgan', 'Commodity', 'Finance', 20.36, 4900781, '2024-11-22');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (111, 4, 'JPMorgan', 'ETF', 'Energy', 1.12, 183758, '2024-03-22');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (112, 5, 'JPMorgan', 'ETF', 'Consumer', 4.55, 3088229, '2024-08-15');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (113, 16, 'Google', 'ETF', 'Technology', 9.85, 3627087, '2024-11-21');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (114, 5, 'Microsoft', 'Bond', 'Finance', 4.04, 2909521, '2025-01-10');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (115, 12, 'Apple Inc', 'Equity', 'Technology', 15.4, 2282391, '2024-08-22');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (116, 6, 'Tesla', 'Commodity', 'Healthcare', 13.43, 2575814, '2024-12-06');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (117, 9, 'US Treasury Bonds', 'Bond', 'Finance', 15.25, 828514, '2024-03-30');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (118, 12, 'JPMorgan', 'ETF', 'Energy', 24.23, 3313353, '2025-02-07');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (119, 11, 'Nvidia', 'ETF', 'Healthcare', 1.82, 4524902, '2024-06-15');
INSERT INTO portfolio_holdings 
(holding_id, portfolio_id, asset_name, asset_type, sector, allocation_percentage, market_value, last_updated)
VALUES (120, 19, 'Google', 'Bond', 'Technology', 17.62, 540040, '2025-01-17');
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (1, 'Nvidia', 'Market Volatility', 25, 'Low', 'Market Volatility identified for Nvidia due to market conditions.', '2024-08-20', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (2, 'Tesla', 'Market Volatility', 27, 'Low', 'Market Volatility identified for Tesla due to market conditions.', '2024-03-14', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (3, 'Google', 'Geopolitical Risk', 10, 'Low', 'Geopolitical Risk identified for Google due to market conditions.', '2024-09-22', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (4, 'JPMorgan', 'Liquidity Risk', 7, 'Low', 'Liquidity Risk identified for JPMorgan due to market conditions.', '2024-08-21', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (5, 'Apple Inc', 'Market Volatility', 8, 'Low', 'Market Volatility identified for Apple Inc due to market conditions.', '2024-01-04', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (6, 'JPMorgan', 'Market Volatility', 56, 'Medium', 'Market Volatility identified for JPMorgan due to market conditions.', '2024-08-05', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (7, 'Amazon', 'Liquidity Risk', 60, 'Medium', 'Liquidity Risk identified for Amazon due to market conditions.', '2024-05-19', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (8, 'US Treasury Bonds', 'Geopolitical Risk', 63, 'Medium', 'Geopolitical Risk identified for US Treasury Bonds due to market conditions.', '2024-03-05', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (9, 'Gold ETF', 'Regulatory Risk', 71, 'High', 'Regulatory Risk identified for Gold ETF due to market conditions.', '2024-11-18', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (10, 'JPMorgan', 'Market Volatility', 8, 'Low', 'Market Volatility identified for JPMorgan due to market conditions.', '2024-10-21', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (11, 'Tesla', 'Liquidity Risk', 64, 'Medium', 'Liquidity Risk identified for Tesla due to market conditions.', '2024-09-29', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (12, 'Gold ETF', 'Market Volatility', 30, 'Medium', 'Market Volatility identified for Gold ETF due to market conditions.', '2024-12-21', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (13, 'Oil Futures', 'Market Volatility', 52, 'Medium', 'Market Volatility identified for Oil Futures due to market conditions.', '2024-10-12', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (14, 'Gold ETF', 'Regulatory Risk', 77, 'High', 'Regulatory Risk identified for Gold ETF due to market conditions.', '2024-06-16', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (15, 'Tesla', 'Regulatory Risk', 37, 'Medium', 'Regulatory Risk identified for Tesla due to market conditions.', '2024-06-14', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (16, 'Oil Futures', 'Geopolitical Risk', 58, 'Medium', 'Geopolitical Risk identified for Oil Futures due to market conditions.', '2024-02-02', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (17, 'US Treasury Bonds', 'Regulatory Risk', 74, 'High', 'Regulatory Risk identified for US Treasury Bonds due to market conditions.', '2024-05-06', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (18, 'Microsoft', 'Geopolitical Risk', 86, 'High', 'Geopolitical Risk identified for Microsoft due to market conditions.', '2024-12-15', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (19, 'Gold ETF', 'Regulatory Risk', 9, 'Low', 'Regulatory Risk identified for Gold ETF due to market conditions.', '2024-03-20', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (20, 'JPMorgan', 'Credit Risk', 13, 'Low', 'Credit Risk identified for JPMorgan due to market conditions.', '2024-04-29', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (21, 'Google', 'Regulatory Risk', 87, 'High', 'Regulatory Risk identified for Google due to market conditions.', '2024-11-12', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (22, 'Microsoft', 'Market Volatility', 45, 'Medium', 'Market Volatility identified for Microsoft due to market conditions.', '2024-08-20', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (23, 'Nvidia', 'Regulatory Risk', 24, 'Low', 'Regulatory Risk identified for Nvidia due to market conditions.', '2024-08-12', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (24, 'Amazon', 'Credit Risk', 6, 'Low', 'Credit Risk identified for Amazon due to market conditions.', '2024-01-02', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (25, 'Gold ETF', 'Market Volatility', 14, 'Low', 'Market Volatility identified for Gold ETF due to market conditions.', '2025-01-25', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (26, 'Microsoft', 'Liquidity Risk', 81, 'High', 'Liquidity Risk identified for Microsoft due to market conditions.', '2024-07-24', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (27, 'US Treasury Bonds', 'Regulatory Risk', 76, 'High', 'Regulatory Risk identified for US Treasury Bonds due to market conditions.', '2024-11-03', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (28, 'US Treasury Bonds', 'Market Volatility', 81, 'High', 'Market Volatility identified for US Treasury Bonds due to market conditions.', '2024-02-01', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (29, 'Amazon', 'Credit Risk', 91, 'High', 'Credit Risk identified for Amazon due to market conditions.', '2024-11-23', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (30, 'Tesla', 'Market Volatility', 15, 'Low', 'Market Volatility identified for Tesla due to market conditions.', '2024-02-20', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (31, 'Tesla', 'Market Volatility', 76, 'High', 'Market Volatility identified for Tesla due to market conditions.', '2024-04-16', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (32, 'Google', 'Regulatory Risk', 4, 'Low', 'Regulatory Risk identified for Google due to market conditions.', '2024-07-22', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (33, 'Nvidia', 'Credit Risk', 82, 'High', 'Credit Risk identified for Nvidia due to market conditions.', '2024-10-29', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (34, 'Tesla', 'Geopolitical Risk', 11, 'Low', 'Geopolitical Risk identified for Tesla due to market conditions.', '2024-12-15', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (35, 'Oil Futures', 'Market Volatility', 87, 'High', 'Market Volatility identified for Oil Futures due to market conditions.', '2024-08-05', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (36, 'Microsoft', 'Market Volatility', 69, 'Medium', 'Market Volatility identified for Microsoft due to market conditions.', '2024-09-24', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (37, 'Oil Futures', 'Regulatory Risk', 57, 'Medium', 'Regulatory Risk identified for Oil Futures due to market conditions.', '2024-10-19', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (38, 'US Treasury Bonds', 'Regulatory Risk', 3, 'Low', 'Regulatory Risk identified for US Treasury Bonds due to market conditions.', '2024-12-01', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (39, 'Google', 'Liquidity Risk', 76, 'High', 'Liquidity Risk identified for Google due to market conditions.', '2025-01-23', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (40, 'Tesla', 'Credit Risk', 73, 'High', 'Credit Risk identified for Tesla due to market conditions.', '2024-04-11', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (41, 'Nvidia', 'Geopolitical Risk', 36, 'Medium', 'Geopolitical Risk identified for Nvidia due to market conditions.', '2024-11-12', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (42, 'Tesla', 'Geopolitical Risk', 61, 'Medium', 'Geopolitical Risk identified for Tesla due to market conditions.', '2024-10-09', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (43, 'Google', 'Geopolitical Risk', 30, 'Medium', 'Geopolitical Risk identified for Google due to market conditions.', '2024-02-03', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (44, 'Nvidia', 'Regulatory Risk', 29, 'Low', 'Regulatory Risk identified for Nvidia due to market conditions.', '2024-04-07', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (45, 'Amazon', 'Liquidity Risk', 75, 'High', 'Liquidity Risk identified for Amazon due to market conditions.', '2024-10-13', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (46, 'US Treasury Bonds', 'Credit Risk', 86, 'High', 'Credit Risk identified for US Treasury Bonds due to market conditions.', '2024-12-05', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (47, 'Microsoft', 'Geopolitical Risk', 12, 'Low', 'Geopolitical Risk identified for Microsoft due to market conditions.', '2024-08-14', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (48, 'Amazon', 'Regulatory Risk', 21, 'Low', 'Regulatory Risk identified for Amazon due to market conditions.', '2024-10-19', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (49, 'Tesla', 'Market Volatility', 81, 'High', 'Market Volatility identified for Tesla due to market conditions.', '2025-01-31', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (50, 'Nvidia', 'Credit Risk', 95, 'High', 'Credit Risk identified for Nvidia due to market conditions.', '2024-12-28', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (51, 'Google', 'Geopolitical Risk', 92, 'High', 'Geopolitical Risk identified for Google due to market conditions.', '2024-08-31', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (52, 'Amazon', 'Market Volatility', 6, 'Low', 'Market Volatility identified for Amazon due to market conditions.', '2024-06-22', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (53, 'Google', 'Geopolitical Risk', 13, 'Low', 'Geopolitical Risk identified for Google due to market conditions.', '2024-08-18', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (54, 'Apple Inc', 'Credit Risk', 0, 'Low', 'Credit Risk identified for Apple Inc due to market conditions.', '2024-01-04', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (55, 'Nvidia', 'Regulatory Risk', 11, 'Low', 'Regulatory Risk identified for Nvidia due to market conditions.', '2024-03-17', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (56, 'Gold ETF', 'Liquidity Risk', 34, 'Medium', 'Liquidity Risk identified for Gold ETF due to market conditions.', '2024-10-17', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (57, 'Amazon', 'Regulatory Risk', 21, 'Low', 'Regulatory Risk identified for Amazon due to market conditions.', '2024-02-07', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (58, 'Google', 'Liquidity Risk', 81, 'High', 'Liquidity Risk identified for Google due to market conditions.', '2024-01-22', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (59, 'Gold ETF', 'Market Volatility', 64, 'Medium', 'Market Volatility identified for Gold ETF due to market conditions.', '2025-01-09', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (60, 'Microsoft', 'Geopolitical Risk', 88, 'High', 'Geopolitical Risk identified for Microsoft due to market conditions.', '2024-02-14', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (61, 'Oil Futures', 'Credit Risk', 91, 'High', 'Credit Risk identified for Oil Futures due to market conditions.', '2024-05-05', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (62, 'Nvidia', 'Market Volatility', 9, 'Low', 'Market Volatility identified for Nvidia due to market conditions.', '2024-07-24', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (63, 'US Treasury Bonds', 'Credit Risk', 83, 'High', 'Credit Risk identified for US Treasury Bonds due to market conditions.', '2024-10-30', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (64, 'Oil Futures', 'Liquidity Risk', 48, 'Medium', 'Liquidity Risk identified for Oil Futures due to market conditions.', '2024-03-12', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (65, 'Oil Futures', 'Market Volatility', 2, 'Low', 'Market Volatility identified for Oil Futures due to market conditions.', '2024-01-16', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (66, 'Microsoft', 'Liquidity Risk', 34, 'Medium', 'Liquidity Risk identified for Microsoft due to market conditions.', '2024-02-08', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (67, 'JPMorgan', 'Credit Risk', 93, 'High', 'Credit Risk identified for JPMorgan due to market conditions.', '2024-05-16', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (68, 'Apple Inc', 'Credit Risk', 6, 'Low', 'Credit Risk identified for Apple Inc due to market conditions.', '2024-05-23', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (69, 'Amazon', 'Market Volatility', 9, 'Low', 'Market Volatility identified for Amazon due to market conditions.', '2024-12-31', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (70, 'Apple Inc', 'Market Volatility', 70, 'High', 'Market Volatility identified for Apple Inc due to market conditions.', '2024-08-11', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (71, 'Google', 'Credit Risk', 22, 'Low', 'Credit Risk identified for Google due to market conditions.', '2024-01-16', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (72, 'Google', 'Credit Risk', 82, 'High', 'Credit Risk identified for Google due to market conditions.', '2024-08-07', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (73, 'JPMorgan', 'Liquidity Risk', 39, 'Medium', 'Liquidity Risk identified for JPMorgan due to market conditions.', '2024-10-23', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (74, 'Google', 'Geopolitical Risk', 20, 'Low', 'Geopolitical Risk identified for Google due to market conditions.', '2024-11-04', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (75, 'Nvidia', 'Geopolitical Risk', 17, 'Low', 'Geopolitical Risk identified for Nvidia due to market conditions.', '2025-01-13', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (76, 'Oil Futures', 'Regulatory Risk', 9, 'Low', 'Regulatory Risk identified for Oil Futures due to market conditions.', '2024-12-22', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (77, 'Google', 'Credit Risk', 54, 'Medium', 'Credit Risk identified for Google due to market conditions.', '2024-02-14', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (78, 'Nvidia', 'Credit Risk', 24, 'Low', 'Credit Risk identified for Nvidia due to market conditions.', '2024-04-18', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (79, 'Gold ETF', 'Market Volatility', 9, 'Low', 'Market Volatility identified for Gold ETF due to market conditions.', '2024-07-09', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (80, 'Apple Inc', 'Credit Risk', 70, 'High', 'Credit Risk identified for Apple Inc due to market conditions.', '2024-03-19', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (81, 'JPMorgan', 'Geopolitical Risk', 71, 'High', 'Geopolitical Risk identified for JPMorgan due to market conditions.', '2024-03-05', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (82, 'Tesla', 'Geopolitical Risk', 33, 'Medium', 'Geopolitical Risk identified for Tesla due to market conditions.', '2024-09-08', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (83, 'Tesla', 'Credit Risk', 80, 'High', 'Credit Risk identified for Tesla due to market conditions.', '2024-10-25', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (84, 'Microsoft', 'Liquidity Risk', 26, 'Low', 'Liquidity Risk identified for Microsoft due to market conditions.', '2024-01-20', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (85, 'Amazon', 'Credit Risk', 91, 'High', 'Credit Risk identified for Amazon due to market conditions.', '2025-01-15', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (86, 'Microsoft', 'Geopolitical Risk', 33, 'Medium', 'Geopolitical Risk identified for Microsoft due to market conditions.', '2025-02-04', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (87, 'Apple Inc', 'Regulatory Risk', 0, 'Low', 'Regulatory Risk identified for Apple Inc due to market conditions.', '2024-06-04', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (88, 'US Treasury Bonds', 'Geopolitical Risk', 49, 'Medium', 'Geopolitical Risk identified for US Treasury Bonds due to market conditions.', '2024-02-03', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (89, 'Google', 'Regulatory Risk', 70, 'High', 'Regulatory Risk identified for Google due to market conditions.', '2024-05-05', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (90, 'Microsoft', 'Geopolitical Risk', 16, 'Low', 'Geopolitical Risk identified for Microsoft due to market conditions.', '2024-11-12', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (91, 'Tesla', 'Market Volatility', 82, 'High', 'Market Volatility identified for Tesla due to market conditions.', '2024-12-08', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (92, 'Gold ETF', 'Market Volatility', 62, 'Medium', 'Market Volatility identified for Gold ETF due to market conditions.', '2025-02-06', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (93, 'Oil Futures', 'Regulatory Risk', 64, 'Medium', 'Regulatory Risk identified for Oil Futures due to market conditions.', '2024-06-17', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (94, 'Microsoft', 'Credit Risk', 71, 'High', 'Credit Risk identified for Microsoft due to market conditions.', '2024-03-30', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (95, 'Apple Inc', 'Geopolitical Risk', 97, 'High', 'Geopolitical Risk identified for Apple Inc due to market conditions.', '2025-01-26', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (96, 'US Treasury Bonds', 'Regulatory Risk', 5, 'Low', 'Regulatory Risk identified for US Treasury Bonds due to market conditions.', '2024-03-14', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (97, 'Tesla', 'Credit Risk', 28, 'Low', 'Credit Risk identified for Tesla due to market conditions.', '2024-06-11', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (98, 'Apple Inc', 'Regulatory Risk', 49, 'Medium', 'Regulatory Risk identified for Apple Inc due to market conditions.', '2024-01-14', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (99, 'Google', 'Regulatory Risk', 28, 'Low', 'Regulatory Risk identified for Google due to market conditions.', '2025-02-20', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (100, 'Amazon', 'Liquidity Risk', 1, 'Low', 'Liquidity Risk identified for Amazon due to market conditions.', '2024-08-30', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (101, 'US Treasury Bonds', 'Liquidity Risk', 45, 'Medium', 'Liquidity Risk identified for US Treasury Bonds due to market conditions.', '2024-10-23', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (102, 'Google', 'Geopolitical Risk', 72, 'High', 'Geopolitical Risk identified for Google due to market conditions.', '2024-06-08', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (103, 'Oil Futures', 'Regulatory Risk', 52, 'Medium', 'Regulatory Risk identified for Oil Futures due to market conditions.', '2024-06-29', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (104, 'Amazon', 'Credit Risk', 3, 'Low', 'Credit Risk identified for Amazon due to market conditions.', '2024-06-10', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (105, 'Oil Futures', 'Credit Risk', 28, 'Low', 'Credit Risk identified for Oil Futures due to market conditions.', '2024-11-10', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (106, 'Amazon', 'Liquidity Risk', 3, 'Low', 'Liquidity Risk identified for Amazon due to market conditions.', '2024-05-04', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (107, 'Nvidia', 'Geopolitical Risk', 11, 'Low', 'Geopolitical Risk identified for Nvidia due to market conditions.', '2025-02-09', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (108, 'Amazon', 'Liquidity Risk', 23, 'Low', 'Liquidity Risk identified for Amazon due to market conditions.', '2024-06-10', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (109, 'Tesla', 'Liquidity Risk', 58, 'Medium', 'Liquidity Risk identified for Tesla due to market conditions.', '2024-04-18', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (110, 'Gold ETF', 'Liquidity Risk', 33, 'Medium', 'Liquidity Risk identified for Gold ETF due to market conditions.', '2024-06-18', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (111, 'Microsoft', 'Market Volatility', 25, 'Low', 'Market Volatility identified for Microsoft due to market conditions.', '2024-09-05', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (112, 'Oil Futures', 'Credit Risk', 98, 'High', 'Credit Risk identified for Oil Futures due to market conditions.', '2024-02-29', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (113, 'Tesla', 'Market Volatility', 19, 'Low', 'Market Volatility identified for Tesla due to market conditions.', '2024-02-24', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (114, 'Apple Inc', 'Geopolitical Risk', 93, 'High', 'Geopolitical Risk identified for Apple Inc due to market conditions.', '2025-01-15', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (115, 'Tesla', 'Liquidity Risk', 40, 'Medium', 'Liquidity Risk identified for Tesla due to market conditions.', '2024-07-23', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (116, 'US Treasury Bonds', 'Regulatory Risk', 60, 'Medium', 'Regulatory Risk identified for US Treasury Bonds due to market conditions.', '2024-08-01', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (117, 'US Treasury Bonds', 'Liquidity Risk', 36, 'Medium', 'Liquidity Risk identified for US Treasury Bonds due to market conditions.', '2025-01-30', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (118, 'Tesla', 'Market Volatility', 80, 'High', 'Market Volatility identified for Tesla due to market conditions.', '2024-07-07', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (119, 'Apple Inc', 'Market Volatility', 34, 'Medium', 'Market Volatility identified for Apple Inc due to market conditions.', '2024-07-31', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (120, 'Google', 'Market Volatility', 64, 'Medium', 'Market Volatility identified for Google due to market conditions.', '2024-09-21', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (121, 'Apple Inc', 'Regulatory Risk', 87, 'High', 'Regulatory Risk identified for Apple Inc due to market conditions.', '2024-01-17', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (122, 'Amazon', 'Geopolitical Risk', 33, 'Medium', 'Geopolitical Risk identified for Amazon due to market conditions.', '2024-05-03', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (123, 'Oil Futures', 'Market Volatility', 16, 'Low', 'Market Volatility identified for Oil Futures due to market conditions.', '2025-02-18', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (124, 'Google', 'Credit Risk', 21, 'Low', 'Credit Risk identified for Google due to market conditions.', '2024-11-26', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (125, 'Google', 'Credit Risk', 32, 'Medium', 'Credit Risk identified for Google due to market conditions.', '2024-11-25', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (126, 'Apple Inc', 'Geopolitical Risk', 50, 'Medium', 'Geopolitical Risk identified for Apple Inc due to market conditions.', '2024-12-21', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (127, 'Amazon', 'Market Volatility', 61, 'Medium', 'Market Volatility identified for Amazon due to market conditions.', '2024-11-26', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (128, 'US Treasury Bonds', 'Credit Risk', 39, 'Medium', 'Credit Risk identified for US Treasury Bonds due to market conditions.', '2024-04-24', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (129, 'Nvidia', 'Liquidity Risk', 23, 'Low', 'Liquidity Risk identified for Nvidia due to market conditions.', '2024-06-17', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (130, 'Amazon', 'Geopolitical Risk', 21, 'Low', 'Geopolitical Risk identified for Amazon due to market conditions.', '2024-11-15', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (131, 'JPMorgan', 'Liquidity Risk', 6, 'Low', 'Liquidity Risk identified for JPMorgan due to market conditions.', '2024-02-19', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (132, 'US Treasury Bonds', 'Liquidity Risk', 23, 'Low', 'Liquidity Risk identified for US Treasury Bonds due to market conditions.', '2024-02-15', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (133, 'US Treasury Bonds', 'Regulatory Risk', 28, 'Low', 'Regulatory Risk identified for US Treasury Bonds due to market conditions.', '2025-01-05', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (134, 'Microsoft', 'Regulatory Risk', 51, 'Medium', 'Regulatory Risk identified for Microsoft due to market conditions.', '2025-01-09', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (135, 'Nvidia', 'Liquidity Risk', 17, 'Low', 'Liquidity Risk identified for Nvidia due to market conditions.', '2024-05-22', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (136, 'Google', 'Credit Risk', 74, 'High', 'Credit Risk identified for Google due to market conditions.', '2024-10-29', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (137, 'Gold ETF', 'Liquidity Risk', 86, 'High', 'Liquidity Risk identified for Gold ETF due to market conditions.', '2024-03-25', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (138, 'Amazon', 'Regulatory Risk', 66, 'Medium', 'Regulatory Risk identified for Amazon due to market conditions.', '2025-02-19', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (139, 'Microsoft', 'Geopolitical Risk', 30, 'Medium', 'Geopolitical Risk identified for Microsoft due to market conditions.', '2024-06-02', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (140, 'US Treasury Bonds', 'Market Volatility', 2, 'Low', 'Market Volatility identified for US Treasury Bonds due to market conditions.', '2024-08-12', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (141, 'Amazon', 'Liquidity Risk', 96, 'High', 'Liquidity Risk identified for Amazon due to market conditions.', '2024-06-05', TRUE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (142, 'JPMorgan', 'Market Volatility', 48, 'Medium', 'Market Volatility identified for JPMorgan due to market conditions.', '2024-09-14', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (143, 'Microsoft', 'Regulatory Risk', 61, 'Medium', 'Regulatory Risk identified for Microsoft due to market conditions.', '2024-07-14', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (144, 'Google', 'Liquidity Risk', 0, 'Low', 'Liquidity Risk identified for Google due to market conditions.', '2024-05-11', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (145, 'Google', 'Liquidity Risk', 27, 'Low', 'Liquidity Risk identified for Google due to market conditions.', '2024-05-23', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (146, 'JPMorgan', 'Liquidity Risk', 52, 'Medium', 'Liquidity Risk identified for JPMorgan due to market conditions.', '2024-06-20', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (147, 'JPMorgan', 'Market Volatility', 20, 'Low', 'Market Volatility identified for JPMorgan due to market conditions.', '2025-02-02', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (148, 'Google', 'Regulatory Risk', 72, 'High', 'Regulatory Risk identified for Google due to market conditions.', '2024-03-26', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (149, 'Amazon', 'Credit Risk', 72, 'High', 'Credit Risk identified for Amazon due to market conditions.', '2024-10-14', FALSE);
INSERT INTO asset_risk_logs 
(risk_id, asset_name, risk_type, risk_score, risk_level, risk_description, assessment_date, escalation_flag)
VALUES (150, 'JPMorgan', 'Credit Risk', 31, 'Medium', 'Credit Risk identified for JPMorgan due to market conditions.', '2024-07-20', FALSE);
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (1, 'Consumer Confidence Index', 'US', 9.52, '2024-01-15', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (2, 'Inflation Rate', 'Europe', 1.73, '2024-05-10', 'Increasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (3, 'Inflation Rate', 'Asia', 4.47, '2025-01-27', 'Increasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (4, 'Consumer Confidence Index', 'Europe', 2.16, '2024-03-19', 'Increasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (5, 'Consumer Confidence Index', 'US', 4.68, '2024-02-16', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (6, 'GDP Growth', 'US', 4.66, '2024-01-06', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (7, 'GDP Growth', 'Asia', 4.59, '2024-06-05', 'Increasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (8, 'Inflation Rate', 'Asia', 9.11, '2025-01-21', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (9, 'Consumer Confidence Index', 'Global', 4.83, '2024-09-19', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (10, 'Inflation Rate', 'Europe', 1.35, '2024-11-24', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (11, 'Unemployment Rate', 'Asia', 5.06, '2024-10-20', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (12, 'Interest Rate', 'US', 3.81, '2024-11-16', 'Increasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (13, 'GDP Growth', 'Europe', 3.57, '2025-01-13', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (14, 'Unemployment Rate', 'Asia', 9.43, '2024-06-27', 'Increasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (15, 'GDP Growth', 'US', 5.66, '2024-11-01', 'Increasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (16, 'Inflation Rate', 'Global', 2.9, '2024-08-21', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (17, 'Unemployment Rate', 'Asia', 2.81, '2024-11-24', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (18, 'GDP Growth', 'Asia', 3.43, '2024-12-12', 'Increasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (19, 'GDP Growth', 'Asia', 8.62, '2024-10-03', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (20, 'Unemployment Rate', 'Asia', 1.42, '2024-02-03', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (21, 'Inflation Rate', 'Asia', 7.57, '2024-07-07', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (22, 'Interest Rate', 'Europe', 5.31, '2024-05-27', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (23, 'Inflation Rate', 'Europe', 6.35, '2025-02-08', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (24, 'Interest Rate', 'Global', 7.19, '2024-10-09', 'Increasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (25, 'Interest Rate', 'US', 1.33, '2024-01-13', 'Increasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (26, 'Interest Rate', 'Europe', 9.56, '2025-01-11', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (27, 'Inflation Rate', 'Europe', 7.56, '2024-02-27', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (28, 'Consumer Confidence Index', 'Europe', 3.22, '2024-07-08', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (29, 'Inflation Rate', 'Global', 2.45, '2024-01-28', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (30, 'Inflation Rate', 'Asia', 4.05, '2025-02-19', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (31, 'Inflation Rate', 'Global', 1.45, '2024-02-02', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (32, 'Consumer Confidence Index', 'Europe', 3.82, '2024-03-23', 'Increasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (33, 'Inflation Rate', 'Europe', 9.84, '2024-09-03', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (34, 'Consumer Confidence Index', 'Europe', 3.9, '2024-01-05', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (35, 'Unemployment Rate', 'Asia', 4.87, '2024-09-17', 'Increasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (36, 'Interest Rate', 'Global', 5.44, '2025-01-11', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (37, 'Inflation Rate', 'Europe', 2.49, '2024-07-16', 'Increasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (38, 'Inflation Rate', 'Europe', 2.75, '2024-10-09', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (39, 'Consumer Confidence Index', 'Asia', 6.7, '2024-04-05', 'Increasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (40, 'Consumer Confidence Index', 'Asia', 2.34, '2024-03-15', 'Increasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (41, 'GDP Growth', 'Europe', 2.17, '2024-05-18', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (42, 'Consumer Confidence Index', 'Global', 6.92, '2024-09-26', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (43, 'Inflation Rate', 'Global', 9.25, '2024-09-25', 'Increasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (44, 'GDP Growth', 'Asia', 9.49, '2024-01-28', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (45, 'Interest Rate', 'US', 7.15, '2024-10-14', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (46, 'Inflation Rate', 'Asia', 9.28, '2024-11-17', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (47, 'Inflation Rate', 'Global', 6.0, '2024-02-26', 'Increasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (48, 'GDP Growth', 'Europe', 2.74, '2024-10-26', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (49, 'Interest Rate', 'US', 4.66, '2025-02-26', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (50, 'Interest Rate', 'Europe', 8.28, '2024-08-14', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (51, 'Unemployment Rate', 'Global', 7.69, '2024-10-24', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (52, 'Consumer Confidence Index', 'US', 7.62, '2025-02-07', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (53, 'Unemployment Rate', 'Global', 6.06, '2024-12-01', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (54, 'Interest Rate', 'Europe', 3.22, '2024-01-10', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (55, 'GDP Growth', 'US', 1.72, '2024-01-06', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (56, 'GDP Growth', 'Global', 1.78, '2024-11-13', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (57, 'Unemployment Rate', 'Global', 6.45, '2025-02-11', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (58, 'Unemployment Rate', 'Europe', 7.27, '2024-02-21', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (59, 'GDP Growth', 'Asia', 1.18, '2024-10-18', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (60, 'GDP Growth', 'US', 4.56, '2024-05-22', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (61, 'Interest Rate', 'Global', 6.04, '2025-01-06', 'Increasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (62, 'GDP Growth', 'Global', 9.01, '2024-04-14', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (63, 'Consumer Confidence Index', 'Global', 4.45, '2024-07-08', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (64, 'Unemployment Rate', 'Asia', 5.79, '2024-10-08', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (65, 'GDP Growth', 'Global', 8.12, '2024-02-04', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (66, 'Interest Rate', 'US', 2.28, '2025-01-31', 'Increasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (67, 'Inflation Rate', 'Asia', 8.94, '2024-06-06', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (68, 'Unemployment Rate', 'Europe', 3.36, '2024-12-20', 'Increasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (69, 'GDP Growth', 'Global', 3.17, '2024-06-28', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (70, 'Unemployment Rate', 'Global', 5.93, '2024-09-23', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (71, 'GDP Growth', 'Global', 7.28, '2024-01-05', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (72, 'Interest Rate', 'Europe', 7.72, '2024-07-20', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (73, 'Interest Rate', 'Asia', 4.67, '2024-07-13', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (74, 'Interest Rate', 'US', 4.95, '2025-01-12', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (75, 'Consumer Confidence Index', 'Global', 3.02, '2024-12-23', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (76, 'Interest Rate', 'Asia', 3.33, '2024-01-27', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (77, 'Unemployment Rate', 'Asia', 3.94, '2025-01-22', 'Increasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (78, 'GDP Growth', 'Global', 6.44, '2025-02-03', 'Stable');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (79, 'Unemployment Rate', 'Global', 3.59, '2024-01-22', 'Decreasing');
INSERT INTO market_indicators
(indicator_id, indicator_name, region, indicator_value, measurement_date, trend_direction)
VALUES (80, 'Unemployment Rate', 'US', 7.08, '2024-12-23', 'Decreasing');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (1, 1, 'Apple Inc', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 122, '2025-02-05', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (2, 3, 'Microsoft', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 139, '2025-01-01', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (3, 6, 'Gold ETF', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 26, '2024-06-20', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (4, 18, 'Microsoft', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 24, '2024-04-30', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (5, 16, 'Gold ETF', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 120, '2024-08-11', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (6, 8, 'Nvidia', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 14, '2024-03-11', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (7, 15, 'Amazon', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 26, '2024-10-01', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (8, 3, 'Apple Inc', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 86, '2024-09-04', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (9, 11, 'Apple Inc', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 89, '2024-06-06', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (10, 4, 'JPMorgan', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 21, '2025-02-14', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (11, 17, 'Gold ETF', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 11, '2024-02-19', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (12, 20, 'Google', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 16, '2024-12-03', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (13, 15, 'JPMorgan', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 94, '2025-01-24', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (14, 16, 'Tesla', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 148, '2024-05-08', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (15, 17, 'Amazon', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 97, '2024-06-11', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (16, 8, 'JPMorgan', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 22, '2024-01-11', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (17, 17, 'Google', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 81, '2024-08-14', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (18, 13, 'Oil Futures', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 1, '2024-12-06', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (19, 9, 'Microsoft', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 14, '2025-01-17', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (20, 6, 'Gold ETF', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 73, '2024-07-26', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (21, 11, 'JPMorgan', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 113, '2024-05-28', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (22, 15, 'Microsoft', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 5, '2024-10-21', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (23, 9, 'Apple Inc', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 22, '2024-04-23', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (24, 6, 'Amazon', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 150, '2024-01-31', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (25, 12, 'Microsoft', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 20, '2024-09-14', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (26, 9, 'JPMorgan', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 32, '2024-07-04', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (27, 2, 'Microsoft', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 53, '2024-08-05', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (28, 5, 'Oil Futures', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 120, '2024-01-31', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (29, 10, 'JPMorgan', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 23, '2024-12-31', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (30, 9, 'Apple Inc', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 78, '2024-02-15', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (31, 14, 'Oil Futures', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 8, '2024-04-12', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (32, 5, 'Microsoft', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 48, '2024-01-21', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (33, 7, 'Google', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 22, '2025-02-16', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (34, 17, 'Tesla', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 102, '2024-06-10', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (35, 15, 'Amazon', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 41, '2025-02-07', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (36, 4, 'JPMorgan', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 119, '2024-09-15', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (37, 4, 'Gold ETF', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 105, '2025-01-22', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (38, 11, 'Microsoft', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 71, '2024-09-20', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (39, 17, 'Apple Inc', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 68, '2024-09-09', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (40, 13, 'Gold ETF', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 90, '2024-06-09', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (41, 5, 'Nvidia', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 138, '2024-06-02', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (42, 9, 'Nvidia', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 128, '2024-04-20', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (43, 12, 'Oil Futures', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 42, '2024-11-21', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (44, 12, 'Microsoft', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 111, '2024-08-30', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (45, 13, 'Nvidia', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 137, '2024-10-29', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (46, 2, 'JPMorgan', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 85, '2024-11-14', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (47, 6, 'JPMorgan', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 13, '2025-01-09', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (48, 7, 'Nvidia', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 83, '2024-11-17', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (49, 6, 'Tesla', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 22, '2024-08-16', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (50, 13, 'Oil Futures', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 13, '2024-10-16', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (51, 9, 'Apple Inc', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 122, '2024-09-11', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (52, 16, 'Oil Futures', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 91, '2024-11-14', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (53, 15, 'JPMorgan', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 150, '2024-11-22', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (54, 20, 'Apple Inc', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 30, '2024-06-21', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (55, 16, 'US Treasury Bonds', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 15, '2024-12-11', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (56, 1, 'Gold ETF', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 66, '2024-10-13', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (57, 19, 'Oil Futures', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 120, '2024-02-21', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (58, 4, 'Tesla', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 85, '2024-09-11', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (59, 18, 'Microsoft', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 143, '2024-02-12', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (60, 16, 'Tesla', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 43, '2024-10-19', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (61, 12, 'Nvidia', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 20, '2025-02-06', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (62, 7, 'US Treasury Bonds', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 36, '2024-11-27', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (63, 16, 'Apple Inc', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 41, '2024-02-02', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (64, 8, 'Nvidia', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 101, '2024-03-22', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (65, 6, 'JPMorgan', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 57, '2024-09-24', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (66, 5, 'JPMorgan', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 141, '2024-03-27', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (67, 2, 'Microsoft', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 48, '2024-07-16', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (68, 4, 'US Treasury Bonds', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 89, '2024-02-21', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (69, 15, 'Microsoft', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 76, '2025-01-12', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (70, 1, 'Tesla', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 65, '2024-12-01', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (71, 13, 'Nvidia', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 76, '2024-03-30', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (72, 3, 'Google', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 3, '2024-04-11', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (73, 6, 'Google', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 95, '2024-10-01', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (74, 6, 'Google', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 111, '2024-12-12', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (75, 15, 'Gold ETF', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 140, '2024-09-07', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (76, 12, 'Google', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 107, '2024-10-27', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (77, 12, 'Oil Futures', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 84, '2024-10-20', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (78, 16, 'Google', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 114, '2024-09-30', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (79, 17, 'JPMorgan', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 50, '2024-08-02', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (80, 19, 'Gold ETF', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 73, '2024-01-25', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (81, 14, 'Google', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 45, '2024-02-17', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (82, 13, 'Tesla', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 148, '2024-10-07', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (83, 2, 'Google', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 135, '2025-01-23', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (84, 9, 'JPMorgan', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 82, '2024-05-13', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (85, 3, 'Microsoft', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 109, '2024-04-24', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (86, 3, 'Tesla', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 3, '2025-02-18', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (87, 4, 'Tesla', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 95, '2024-01-15', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (88, 17, 'Amazon', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 115, '2024-05-17', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (89, 7, 'Apple Inc', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 105, '2024-11-30', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (90, 7, 'Tesla', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 127, '2024-09-02', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (91, 1, 'Tesla', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 1, '2024-06-01', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (92, 10, 'Apple Inc', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 95, '2024-08-07', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (93, 16, 'Tesla', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 69, '2024-11-05', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (94, 2, 'US Treasury Bonds', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 77, '2024-03-12', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (95, 17, 'Amazon', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 109, '2024-08-10', 'Rejected');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (96, 16, 'Google', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 147, '2024-03-11', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (97, 1, 'Microsoft', 'HOLD', 'Decision based on market trend and portfolio diversification strategy.', 69, '2024-05-19', 'Pending');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (98, 4, 'Google', 'BUY', 'Decision based on market trend and portfolio diversification strategy.', 33, '2024-01-13', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (99, 19, 'Microsoft', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 107, '2024-01-26', 'Approved');
INSERT INTO investment_decisions
(decision_id, portfolio_id, asset_name, decision_type, decision_reason, risk_assessment_reference, decision_date, approval_status)
VALUES (100, 16, 'Oil Futures', 'SELL', 'Decision based on market trend and portfolio diversification strategy.', 112, '2024-02-01', 'Rejected');
