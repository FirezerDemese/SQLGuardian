-- SQLGuardian Blocking Simulator
-- Run in Tab 1 - holds locks for 90 seconds
-- Open dashboard now and watch blocking section light up

USE WideWorldImporters;
GO

PRINT 'Blocking simulation starting - holds locks for 90 seconds';
PRINT 'Start simulate_workload.sql in another tab NOW';
PRINT 'Then check SQLGuardian dashboard - blocking section will show active sessions';

BEGIN TRANSACTION;

    -- Lock orders rows without committing
    UPDATE Sales.Orders
    SET Comments = 'Locked by ETL process - do not touch'
    WHERE OrderID BETWEEN 1 AND 10;

    -- Lock invoice rows
    UPDATE Sales.Invoices
    SET Comments = 'Processing'
    WHERE InvoiceID BETWEEN 1 AND 10;

    -- Lock customer rows  
    UPDATE Sales.Customers
    SET DeliveryAddressLine1 = DeliveryAddressLine1
    WHERE CustomerID BETWEEN 1 AND 20;

    PRINT 'Locks acquired on Sales.Orders, Sales.Invoices, Sales.Customers';
    PRINT 'Waiting 90 seconds - check SQLGuardian dashboard NOW';

    WAITFOR DELAY '00:01:30';

ROLLBACK TRANSACTION;
PRINT 'Done - locks released';
GO
