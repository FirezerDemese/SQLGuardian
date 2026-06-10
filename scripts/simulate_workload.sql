-- SQLGuardian Workload Simulator
-- Run in Tab 2 AFTER starting blocking sim
-- Queries hit the same locked rows - creates real blocking chains

USE WideWorldImporters;
GO

PRINT 'Workload simulation starting - runs for 3 minutes';
DECLARE @i INT = 0;
DECLARE @start DATETIME2 = GETDATE();

WHILE DATEDIFF(SECOND, @start, GETDATE()) < 180
BEGIN
    SET @i = @i + 1;

    -- This will BLOCK if blocking sim is running (hits same Orders rows)
    SELECT TOP 20
        o.OrderID,
        o.OrderDate,
        c.CustomerName,
        SUM(ol.Quantity * ol.UnitPrice) AS OrderTotal
    FROM Sales.Orders o
    JOIN Sales.Customers c ON o.CustomerID = c.CustomerID
    JOIN Sales.OrderLines ol ON o.OrderID = ol.OrderID
    WHERE o.OrderID BETWEEN 1 AND 10
    GROUP BY o.OrderID, o.OrderDate, c.CustomerName
    ORDER BY o.OrderDate DESC;

    -- Invoice lookup - also blocked
    SELECT TOP 10
        i.InvoiceID,
        i.InvoiceDate,
        c.CustomerName,
        i.TotalDryItems,
        i.TotalChillerItems
    FROM Sales.Invoices i
    JOIN Sales.Customers c ON i.CustomerID = c.CustomerID
    WHERE i.InvoiceID BETWEEN 1 AND 10;

    -- Supplier query (not blocked - just adds workload)
    SELECT TOP 20
        s.SupplierName,
        s.SupplierCategoryID,
        COUNT(po.PurchaseOrderID) AS TotalPOs
    FROM Purchasing.Suppliers s
    LEFT JOIN Purchasing.PurchaseOrders po ON s.SupplierID = po.SupplierID
    GROUP BY s.SupplierName, s.SupplierCategoryID
    ORDER BY TotalPOs DESC;

    -- Stock query (not blocked - adds wait stats)
    SELECT TOP 30
        si.StockItemName,
        si.UnitPrice,
        si.QuantityPerOuter,
        sih.QuantityOnHand,
        sih.BinLocation
    FROM Warehouse.StockItems si
    JOIN Warehouse.StockItemHoldings sih ON si.StockItemID = sih.StockItemID
    ORDER BY sih.QuantityOnHand ASC;

    -- Cross-db hit on AdventureWorks
    USE AdventureWorks2022;
    SELECT TOP 5
        soh.SalesOrderID,
        soh.TotalDue
    FROM Sales.SalesOrderHeader soh
    ORDER BY soh.TotalDue DESC;
    USE WideWorldImporters;

    WAITFOR DELAY '00:00:02';

    IF @i % 5 = 0
        PRINT 'Iteration ' + CAST(@i AS VARCHAR) + ' | elapsed: ' + CAST(DATEDIFF(SECOND, @start, GETDATE()) AS VARCHAR) + 's';
END;

PRINT 'Workload complete - ' + CAST(@i AS VARCHAR) + ' iterations';
GO
