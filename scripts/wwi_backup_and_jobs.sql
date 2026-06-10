-- Backup WideWorldImporters and add a WWI-specific job
USE master;
GO

-- Backup WWI so it doesn't show "Never" in the dashboard
BACKUP DATABASE [WideWorldImporters]
TO DISK = N'/var/opt/mssql/data/WideWorldImporters_backup.bak'
WITH FORMAT, INIT, COMPRESSION,
NAME = N'WideWorldImporters-Full',
STATS = 25;
GO

PRINT 'WideWorldImporters backed up successfully';
GO

-- Add a WWI-specific agent job
USE msdb;
GO

IF EXISTS (SELECT 1 FROM sysjobs WHERE name = 'ETL - WWI Daily Order Processing')
    EXEC sp_delete_job @job_name = N'ETL - WWI Daily Order Processing', @delete_unused_schedule = 1;
GO

EXEC sp_add_job
    @job_name = N'ETL - WWI Daily Order Processing',
    @enabled = 1,
    @description = N'Processes daily orders in WideWorldImporters - picks, packs, invoices';

EXEC sp_add_jobstep
    @job_name = N'ETL - WWI Daily Order Processing',
    @step_name = N'Process Orders',
    @command = N'
        USE WideWorldImporters;
        -- Simulate order processing work
        SELECT COUNT(*) AS PendingOrders
        FROM Sales.Orders
        WHERE PickingCompletedWhen IS NULL
          AND OrderDate < GETDATE();
        SELECT COUNT(*) AS PendingInvoices
        FROM Sales.Orders o
        WHERE NOT EXISTS (
            SELECT 1 FROM Sales.Invoices i WHERE i.OrderID = o.OrderID
        )
        AND o.OrderDate < DATEADD(DAY, -1, GETDATE());
    ',
    @subsystem = N'TSQL';

EXEC sp_add_schedule
    @schedule_name = N'WWI_Order_Processing_Nightly',
    @freq_type = 4,
    @freq_interval = 1,
    @freq_recurrence_factor = 1,
    @active_start_time = 10000;

EXEC sp_attach_schedule
    @job_name = N'ETL - WWI Daily Order Processing',
    @schedule_name = N'WWI_Order_Processing_Nightly';

EXEC sp_add_jobserver
    @job_name = N'ETL - WWI Daily Order Processing',
    @server_name = N'(local)';

PRINT 'Created: ETL - WWI Daily Order Processing';
GO

-- Run it once to create history
EXEC sp_start_job @job_name = N'ETL - WWI Daily Order Processing';
GO
WAITFOR DELAY '00:00:05';
GO

PRINT '=== WideWorldImporters setup complete ===';
PRINT 'Refresh your SQLGuardian dashboard';
GO
