-- SQLGuardian Long-Running Query Simulator
-- Creates a query that runs 45+ seconds to trigger long query detection
-- Run in a SEPARATE terminal tab

USE WideWorldImporters;
GO

PRINT 'Starting long-running query simulation (45 seconds)...';
PRINT 'Check SQLGuardian dashboard - should appear in monitoring within 30s';

-- Intentionally slow cross-database aggregation
-- Uses OPTION(MAXDOP 1) to prevent parallelism and ensure it runs slow
SELECT
    c.CustomerName,
    c.CreditLimit,
    COUNT(DISTINCT o.OrderID) AS TotalOrders,
    SUM(ol.Quantity * ol.UnitPrice) AS LifetimeRevenue,
    AVG(ol.UnitPrice) AS AvgUnitPrice,
    MAX(o.OrderDate) AS LastOrderDate,
    MIN(o.OrderDate) AS FirstOrderDate,
    -- Force slow execution with repeated subqueries
    (SELECT COUNT(*) FROM Sales.Orders o2 WHERE o2.CustomerID = c.CustomerID) AS OrderCountCheck,
    (SELECT ISNULL(SUM(ol2.Quantity * ol2.UnitPrice), 0)
     FROM Sales.Orders o2
     JOIN Sales.OrderLines ol2 ON o2.OrderID = ol2.OrderID
     WHERE o2.CustomerID = c.CustomerID
       AND o2.OrderDate >= DATEADD(YEAR, -1, GETDATE())) AS LastYearRevenue
FROM Sales.Customers c
JOIN Sales.Orders o ON c.CustomerID = o.CustomerID
JOIN Sales.OrderLines ol ON o.OrderID = ol.OrderID
GROUP BY c.CustomerName, c.CreditLimit, c.CustomerID
ORDER BY LifetimeRevenue DESC
OPTION (MAXDOP 1, OPTIMIZE FOR UNKNOWN);
GO

PRINT 'Long-running query complete';
GO
