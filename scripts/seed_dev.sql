-- SQLGuardian Dev Seed Script
-- Run this after the SQL Server container is healthy to create test data

USE master;
GO

-- ============================================================
-- 1. Create test databases
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.databases WHERE name = 'GuardianTest_OLTP')
BEGIN
    CREATE DATABASE GuardianTest_OLTP;
    PRINT 'Created GuardianTest_OLTP';
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.databases WHERE name = 'GuardianTest_Reporting')
BEGIN
    CREATE DATABASE GuardianTest_Reporting;
    PRINT 'Created GuardianTest_Reporting';
END
GO

-- ============================================================
-- 2. Create test tables with some data
-- ============================================================
USE GuardianTest_OLTP;
GO

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Orders')
BEGIN
    CREATE TABLE dbo.Orders (
        OrderID     INT IDENTITY(1,1) PRIMARY KEY,
        CustomerID  INT NOT NULL,
        OrderDate   DATETIME2 DEFAULT GETDATE(),
        Amount      DECIMAL(10,2),
        Status      NVARCHAR(20) DEFAULT 'Pending'
    );

    -- Seed 10k rows for realistic query testing
    INSERT INTO dbo.Orders (CustomerID, Amount, Status)
    SELECT
        ABS(CHECKSUM(NEWID())) % 1000 + 1,
        ROUND(RAND(CHECKSUM(NEWID())) * 5000, 2),
        CASE ABS(CHECKSUM(NEWID())) % 3
            WHEN 0 THEN 'Pending'
            WHEN 1 THEN 'Shipped'
            ELSE 'Delivered'
        END
    FROM master.dbo.spt_values a
    CROSS JOIN master.dbo.spt_values b
    WHERE a.type = 'P' AND a.number < 100
      AND b.type = 'P' AND b.number < 100;

    PRINT 'Seeded Orders table';
END
GO

-- ============================================================
-- 3. Create a SQL Agent job for testing job monitoring
-- ============================================================
USE msdb;
GO

IF NOT EXISTS (SELECT 1 FROM msdb.dbo.sysjobs WHERE name = 'GuardianTest_Maintenance')
BEGIN
    EXEC sp_add_job
        @job_name = N'GuardianTest_Maintenance',
        @enabled = 1,
        @description = N'Test maintenance job for SQLGuardian monitoring',
        @category_name = N'Database Maintenance';

    EXEC sp_add_jobstep
        @job_name = N'GuardianTest_Maintenance',
        @step_name = N'Update Stats',
        @command = N'USE GuardianTest_OLTP; UPDATE STATISTICS dbo.Orders;',
        @subsystem = N'TSQL';

    EXEC sp_add_schedule
        @schedule_name = N'GuardianTest_Daily',
        @freq_type = 4,         -- Daily
        @freq_interval = 1,
        @active_start_time = 20000;  -- 02:00 AM

    EXEC sp_attach_schedule
        @job_name = N'GuardianTest_Maintenance',
        @schedule_name = N'GuardianTest_Daily';

    EXEC sp_add_jobserver
        @job_name = N'GuardianTest_Maintenance',
        @server_name = N'(local)';

    PRINT 'Created GuardianTest_Maintenance job';
END
GO

PRINT '=== SQLGuardian seed complete ===';
GO
