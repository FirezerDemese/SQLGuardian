-- SQLGuardian Production Jobs Setup (Fixed)
USE msdb;
GO

PRINT '=== Creating production SQL Agent jobs ===';
GO

-- Clean up any partial jobs from previous run
IF EXISTS (SELECT 1 FROM sysjobs WHERE name = 'ETL - Nightly Sales Load')
    EXEC sp_delete_job @job_name = N'ETL - Nightly Sales Load', @delete_unused_schedule = 1;
IF EXISTS (SELECT 1 FROM sysjobs WHERE name = 'Maintenance - Index Rebuild AdventureWorks')
    EXEC sp_delete_job @job_name = N'Maintenance - Index Rebuild AdventureWorks', @delete_unused_schedule = 1;
IF EXISTS (SELECT 1 FROM sysjobs WHERE name = 'Maintenance - Update Statistics All DBs')
    EXEC sp_delete_job @job_name = N'Maintenance - Update Statistics All DBs', @delete_unused_schedule = 1;
IF EXISTS (SELECT 1 FROM sysjobs WHERE name = 'Backup - AdventureWorks2022 Full')
    EXEC sp_delete_job @job_name = N'Backup - AdventureWorks2022 Full', @delete_unused_schedule = 1;
IF EXISTS (SELECT 1 FROM sysjobs WHERE name = 'Reports - Monthly Sales Summary')
    EXEC sp_delete_job @job_name = N'Reports - Monthly Sales Summary', @delete_unused_schedule = 1;
IF EXISTS (SELECT 1 FROM sysjobs WHERE name = 'GuardianTest_Maintenance')
    EXEC sp_delete_job @job_name = N'GuardianTest_Maintenance', @delete_unused_schedule = 1;
GO

EXEC sp_add_job @job_name = N'ETL - Nightly Sales Load', @enabled = 1, @description = N'Loads daily sales transactions from staging to AdventureWorks';
EXEC sp_add_jobstep @job_name = N'ETL - Nightly Sales Load', @step_name = N'Load Sales Orders', @command = N'USE AdventureWorks2022; SELECT COUNT(*) AS OrderCount FROM Sales.SalesOrderHeader WITH (NOLOCK);', @subsystem = N'TSQL';
EXEC sp_add_schedule @schedule_name = N'ETL_Nightly_2AM', @freq_type = 4, @freq_interval = 1, @freq_recurrence_factor = 1, @active_start_time = 20000;
EXEC sp_attach_schedule @job_name = N'ETL - Nightly Sales Load', @schedule_name = N'ETL_Nightly_2AM';
EXEC sp_add_jobserver @job_name = N'ETL - Nightly Sales Load', @server_name = N'(local)';
PRINT 'Created: ETL - Nightly Sales Load';
GO

EXEC sp_add_job @job_name = N'Maintenance - Index Rebuild AdventureWorks', @enabled = 1, @description = N'Weekly index rebuild on AdventureWorks2022';
EXEC sp_add_jobstep @job_name = N'Maintenance - Index Rebuild AdventureWorks', @step_name = N'Rebuild Indexes', @command = N'USE AdventureWorks2022; ALTER INDEX ALL ON Sales.SalesOrderDetail REORGANIZE; UPDATE STATISTICS Sales.SalesOrderDetail;', @subsystem = N'TSQL';
EXEC sp_add_schedule @schedule_name = N'Maint_Weekly_Sunday', @freq_type = 8, @freq_interval = 1, @freq_recurrence_factor = 1, @active_start_time = 10000;
EXEC sp_attach_schedule @job_name = N'Maintenance - Index Rebuild AdventureWorks', @schedule_name = N'Maint_Weekly_Sunday';
EXEC sp_add_jobserver @job_name = N'Maintenance - Index Rebuild AdventureWorks', @server_name = N'(local)';
PRINT 'Created: Maintenance - Index Rebuild AdventureWorks';
GO

EXEC sp_add_job @job_name = N'Maintenance - Update Statistics All DBs', @enabled = 1, @description = N'Updates statistics on all user databases nightly';
EXEC sp_add_jobstep @job_name = N'Maintenance - Update Statistics All DBs', @step_name = N'Update Stats', @command = N'USE AdventureWorks2022; EXEC sp_updatestats;', @subsystem = N'TSQL';
EXEC sp_add_schedule @schedule_name = N'Stats_Nightly_3AM', @freq_type = 4, @freq_interval = 1, @freq_recurrence_factor = 1, @active_start_time = 30000;
EXEC sp_attach_schedule @job_name = N'Maintenance - Update Statistics All DBs', @schedule_name = N'Stats_Nightly_3AM';
EXEC sp_add_jobserver @job_name = N'Maintenance - Update Statistics All DBs', @server_name = N'(local)';
PRINT 'Created: Maintenance - Update Statistics All DBs';
GO

EXEC sp_add_job @job_name = N'Backup - AdventureWorks2022 Full', @enabled = 1, @description = N'Full nightly backup of AdventureWorks2022';
EXEC sp_add_jobstep @job_name = N'Backup - AdventureWorks2022 Full', @step_name = N'Full Backup', @command = N'BACKUP DATABASE [AdventureWorks2022] TO DISK = N''/var/opt/mssql/data/AdventureWorks2022_backup.bak'' WITH FORMAT, INIT, COMPRESSION, NAME = N''AW2022-Full'', STATS = 25;', @subsystem = N'TSQL';
EXEC sp_add_schedule @schedule_name = N'Backup_Nightly_1AM', @freq_type = 4, @freq_interval = 1, @freq_recurrence_factor = 1, @active_start_time = 10000;
EXEC sp_attach_schedule @job_name = N'Backup - AdventureWorks2022 Full', @schedule_name = N'Backup_Nightly_1AM';
EXEC sp_add_jobserver @job_name = N'Backup - AdventureWorks2022 Full', @server_name = N'(local)';
PRINT 'Created: Backup - AdventureWorks2022 Full';
GO

EXEC sp_add_job @job_name = N'Reports - Monthly Sales Summary', @enabled = 1, @description = N'Monthly sales report - failing due to missing proc';
EXEC sp_add_jobstep @job_name = N'Reports - Monthly Sales Summary', @step_name = N'Generate Report', @command = N'EXEC msdb.dbo.non_existent_report_proc;', @subsystem = N'TSQL', @on_fail_action = 2;
EXEC sp_add_schedule @schedule_name = N'Reports_Monthly', @freq_type = 16, @freq_interval = 1, @freq_recurrence_factor = 1, @active_start_time = 60000;
EXEC sp_attach_schedule @job_name = N'Reports - Monthly Sales Summary', @schedule_name = N'Reports_Monthly';
EXEC sp_add_jobserver @job_name = N'Reports - Monthly Sales Summary', @server_name = N'(local)';
PRINT 'Created: Reports - Monthly Sales Summary';
GO

PRINT 'Running backup job...';
EXEC sp_start_job @job_name = N'Backup - AdventureWorks2022 Full';
GO
WAITFOR DELAY '00:00:15';
GO

PRINT 'Running ETL job...';
EXEC sp_start_job @job_name = N'ETL - Nightly Sales Load';
GO
WAITFOR DELAY '00:00:05';
GO

PRINT 'Running index maintenance...';
EXEC sp_start_job @job_name = N'Maintenance - Index Rebuild AdventureWorks';
GO
WAITFOR DELAY '00:00:08';
GO

PRINT 'Running stats update...';
EXEC sp_start_job @job_name = N'Maintenance - Update Statistics All DBs';
GO
WAITFOR DELAY '00:00:05';
GO

PRINT 'Running report job (will fail)...';
EXEC sp_start_job @job_name = N'Reports - Monthly Sales Summary';
GO
WAITFOR DELAY '00:00:04';
GO

PRINT 'Backing up test databases...';
BACKUP DATABASE [GuardianTest_OLTP] TO DISK = N'/var/opt/mssql/data/GuardianTest_OLTP_backup.bak' WITH FORMAT, INIT, NAME = N'GuardianTest_OLTP-Full', STATS = 25;
GO
BACKUP DATABASE [GuardianTest_Reporting] TO DISK = N'/var/opt/mssql/data/GuardianTest_Reporting_backup.bak' WITH FORMAT, INIT, NAME = N'GuardianTest_Reporting-Full', STATS = 25;
GO

PRINT '';
PRINT '=== Job Results ===';
GO
SELECT
    j.name AS job_name,
    CASE h.run_status WHEN 0 THEN 'Failed' WHEN 1 THEN 'Succeeded' WHEN 4 THEN 'Running' ELSE 'Not run' END AS last_run_status,
    msdb.dbo.agent_datetime(h.run_date, h.run_time) AS last_run_time
FROM msdb.dbo.sysjobs j
LEFT JOIN (
    SELECT jh.*, ROW_NUMBER() OVER (PARTITION BY jh.job_id ORDER BY jh.run_date DESC, jh.run_time DESC) AS rn
    FROM msdb.dbo.sysjobhistory jh WHERE jh.step_id = 0
) h ON j.job_id = h.job_id AND h.rn = 1
ORDER BY j.name;
GO
PRINT '=== Refresh your SQLGuardian dashboard ===';
GO