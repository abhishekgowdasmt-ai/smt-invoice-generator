$ErrorActionPreference = 'Stop'
$psql = 'C:\Program Files\PostgreSQL\16\bin\psql.exe'
$repo = 'C:\Users\user\Downloads\smt-invoice-generator-main\smt-invoice-generator-main'
$schema = Join-Path $repo 'dev-db\001_smt_dev_schema.sql'
$seed = Join-Path $repo 'dev-db\002_branch_seed.sql'
$envFile = Join-Path $repo 'shree-maruthi-travels-main\shree-maruthi-travels-main\.env'
$env:PGHOST = '127.0.0.1'
$env:PGPORT = '5432'
$env:PGUSER = 'postgres'
$env:PGCLIENTENCODING = 'UTF8'
$env:PSQL_HISTORY = Join-Path $env:TEMP 'smt-psql-history.txt'

function Clear-PgPassword {
    $env:PGPASSWORD = $null
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    if (Test-Path $env:PSQL_HISTORY) {
        Remove-Item -Force $env:PSQL_HISTORY -ErrorAction SilentlyContinue
    }
}

function Invoke-Psql {
    param(
        [Parameter(Mandatory = $true)][string]$Database,
        [string]$Sql,
        [string]$File,
        [switch]$TuplesOnly
    )
    $argumentList = @(
        '-h', '127.0.0.1', '-p', '5432', '-U', 'postgres', '-d', $Database,
        '-X', '-v', 'ON_ERROR_STOP=1'
    )
    if ($TuplesOnly) { $argumentList += @('-t', '-A') }
    if ($File) { $argumentList += @('-q', '-f', $File) }
    else { $argumentList += @('-c', $Sql) }
    $rendered = ($argumentList | ForEach-Object {
        if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ }
    }) -join ' '
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $psql
    $psi.Arguments = $rendered
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $psi.EnvironmentVariables['PGPASSWORD'] = [string]$env:PGPASSWORD
    $psi.EnvironmentVariables['PGCLIENTENCODING'] = 'UTF8'
    $psi.EnvironmentVariables['PSQL_HISTORY'] = [string]$env:PSQL_HISTORY
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi
    [void]$process.Start()
    $outTask = $process.StandardOutput.ReadToEndAsync()
    $errTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $stdout = $outTask.Result
    $stderr = $errTask.Result
    foreach ($line in ($stderr -split "`r?`n")) {
        if ($line -match 'WARNING:') { Write-Output ("PSQL_WARNING " + $line.Trim()) }
    }
    if ($process.ExitCode -ne 0) {
        throw ($stderr.Trim() + "`n" + $stdout.Trim())
    }
    return $stdout
}

if (-not (Test-Path $psql)) { Write-Output 'PSQL_MISSING'; exit 1 }
if (-not (Test-Path $schema)) { Write-Output 'SCHEMA_FILE_MISSING'; exit 1 }
if (-not (Test-Path $seed)) { Write-Output 'SEED_FILE_MISSING'; exit 1 }

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$form = New-Object System.Windows.Forms.Form
$form.Text = 'Local PostgreSQL password'
$form.ClientSize = New-Object System.Drawing.Size(440, 150)
$form.StartPosition = 'CenterScreen'
$form.TopMost = $true
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$label = New-Object System.Windows.Forms.Label
$label.SetBounds(12, 12, 416, 52)
$label.Text = "smt_dev exists, but the schema load was rolled back.`r`nEnter the local postgres password again to finish. It is not shown in chat or saved in Git."
$box = New-Object System.Windows.Forms.TextBox
$box.SetBounds(12, 70, 416, 24)
$box.UseSystemPasswordChar = $true
$ok = New-Object System.Windows.Forms.Button
$ok.Text = 'Continue'
$ok.SetBounds(248, 108, 84, 28)
$ok.DialogResult = [System.Windows.Forms.DialogResult]::OK
$cancel = New-Object System.Windows.Forms.Button
$cancel.Text = 'Cancel'
$cancel.SetBounds(340, 108, 84, 28)
$cancel.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
$form.AcceptButton = $ok
$form.CancelButton = $cancel
$form.Controls.AddRange(@($label, $box, $ok, $cancel))
$dialog = $form.ShowDialog()
$entered = $box.Text
$box.Text = ''
$form.Dispose()
if ($dialog -ne [System.Windows.Forms.DialogResult]::OK -or [string]::IsNullOrEmpty($entered)) {
    Write-Output 'PASSWORD_PROMPT_CANCELLED'
    exit 2
}

$env:PGPASSWORD = $entered
$entered = $null

try {
    $version = Invoke-Psql -Database 'postgres' -TuplesOnly -Sql "SELECT current_setting('server_version');"
    Write-Output ("SERVER_VERSION=" + (($version | Out-String).Trim()))

    $exists = Invoke-Psql -Database 'postgres' -TuplesOnly -Sql "SELECT count(*) FROM pg_database WHERE datname = 'smt_dev';"
    if ((($exists | Out-String).Trim()) -ne '0') {
        $existingTables = Invoke-Psql -Database 'smt_dev' -TuplesOnly -Sql "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND c.relkind = 'r';"
        Write-Output ("SMT_DEV_ALREADY_EXISTS tables=" + (($existingTables | Out-String).Trim()))
        if ((($existingTables | Out-String).Trim()) -ne '0') {
            Write-Output 'STOP_EXISTING_DATABASE_HAS_TABLES'
            exit 5
        }
    } else {
        Invoke-Psql -Database 'postgres' -Sql "CREATE DATABASE smt_dev WITH ENCODING 'UTF8' TEMPLATE template0 OWNER postgres;" | Out-Null
        Write-Output 'DATABASE_CREATED'
    }

    Invoke-Psql -Database 'postgres' -Sql "ALTER DATABASE smt_dev SET timezone TO 'Asia/Kolkata';" | Out-Null
    $info = Invoke-Psql -Database 'postgres' -TuplesOnly -Sql "SELECT pg_encoding_to_char(encoding) || '|' || datdba::regrole::text FROM pg_database WHERE datname = 'smt_dev';"
    Write-Output ("DATABASE_INFO=" + (($info | Out-String).Trim()))
    $tz = Invoke-Psql -Database 'smt_dev' -TuplesOnly -Sql "SELECT current_setting('TIMEZONE');"
    Write-Output ("DATABASE_TIMEZONE=" + (($tz | Out-String).Trim()))

    Invoke-Psql -Database 'smt_dev' -File $schema | Out-Null
    Write-Output 'SCHEMA_EXECUTED'

    Invoke-Psql -Database 'smt_dev' -File $seed | Out-Null
    Write-Output 'SEED_EXECUTED'

    $branches = Invoke-Psql -Database 'smt_dev' -TuplesOnly -Sql "SELECT code || '|' || name || '|' || city || '|' || timezone || '|' || active::text FROM branches ORDER BY code;"
    Write-Output 'BRANCHES_BEGIN'
    $branches | ForEach-Object { if ("$_".Trim()) { Write-Output ("BRANCH " + "$_".Trim()) } }
    Write-Output 'BRANCHES_END'
    $dupes = Invoke-Psql -Database 'smt_dev' -TuplesOnly -Sql "SELECT count(*) FROM (SELECT code FROM branches GROUP BY code HAVING count(*) > 1) d;"
    Write-Output ("BRANCH_DUPLICATE_CODES=" + (($dupes | Out-String).Trim()))
    $otherRows = Invoke-Psql -Database 'smt_dev' -TuplesOnly -Sql "SELECT count(*) FROM users;"
    Write-Output ("USERS_ROWS=" + (($otherRows | Out-String).Trim()))

    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    function New-Secret([int]$Size) {
        $bytes = New-Object byte[] $Size
        $rng.GetBytes($bytes)
        return [Convert]::ToBase64String($bytes)
    }
    $appPassword = New-Secret 48
    $staffToken = New-Secret 48
    $jwtSecret = New-Secret 48
    if ($staffToken -eq $jwtSecret) { throw 'secrets were not independent' }

    $sqlPath = Join-Path $env:TEMP ('smt-app-pw-' + [guid]::NewGuid().ToString('N') + '.sql')
    $literal = $appPassword.Replace("'", "''")
    Set-Content -Path $sqlPath -Value "ALTER ROLE smt_app PASSWORD '$literal';" -Encoding ascii -NoNewline
    try {
        Invoke-Psql -Database 'smt_dev' -File $sqlPath | Out-Null
    } catch {
        Write-Output 'SMT_APP_PASSWORD_SET_FAILED'
        exit 4
    } finally {
        if (Test-Path $sqlPath) { Remove-Item -Force $sqlPath }
    }
    Write-Output 'SMT_APP_PASSWORD_SET'

    $savedAdmin = $env:PGPASSWORD
    $env:PGPASSWORD = $appPassword
    $appCheck = & $psql -h 127.0.0.1 -p 5432 -U smt_app -d smt_dev -X -t -A -v ON_ERROR_STOP=1 -c "SELECT current_database() || '|' || current_user || '|' || current_setting('TIMEZONE');" 2>&1
    $appExit = $LASTEXITCODE
    $env:PGPASSWORD = $savedAdmin
    $savedAdmin = $null
    if ($appExit -ne 0) {
        Write-Output 'SMT_APP_CONNECT_FAILED'
        exit 4
    }
    Write-Output ("SMT_APP_CONNECT=" + (($appCheck | Out-String).Trim()))

    $encodedPassword = [uri]::EscapeDataString($appPassword)
    $dsn = "postgresql://smt_app:${encodedPassword}@127.0.0.1:5432/smt_dev"
    if (-not (Test-Path $envFile)) { throw 'application env file is missing' }
    $lines = @(Get-Content -Path $envFile)
    function Set-Key([string[]]$Source, [string]$Key, [string]$Value) {
        $found = $false
        $result = foreach ($line in $Source) {
            if ($line -match "^$([regex]::Escape($Key))=") {
                $found = $true
                "$Key=""$Value"""
            } else {
                $line
            }
        }
        if (-not $found) { $result = @($result) + "$Key=""$Value""" }
        return ,@($result)
    }
    $lines = Set-Key $lines 'STAFF_TOKEN' $staffToken
    $lines = Set-Key $lines 'RAC_JWT_SECRET' $jwtSecret
    $lines = Set-Key $lines 'SMT_DEV_DATABASE_URL' $dsn
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllLines($envFile, $lines, $utf8)
    Write-Output 'ENV_UPDATED keys=STAFF_TOKEN,RAC_JWT_SECRET,SMT_DEV_DATABASE_URL'
    Write-Output ("SECRET_LENGTHS staff=$($staffToken.Length) jwt=$($jwtSecret.Length) independent=$($staffToken -ne $jwtSecret)")

    $expected = @(Select-String -Path $schema -Pattern '^CREATE TABLE (\w+)' | ForEach-Object { $_.Matches[0].Groups[1].Value })
    $actualRaw = Invoke-Psql -Database 'smt_dev' -TuplesOnly -Sql "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND c.relkind = 'r' ORDER BY 1;"
    $actual = @($actualRaw | ForEach-Object { "$_".Trim() } | Where-Object { $_ })
    $missing = @($expected | Where-Object { $_ -notin $actual })
    $extra = @($actual | Where-Object { $_ -notin $expected })
    Write-Output ("TABLE_COUNT=$($actual.Count)")
    Write-Output ("TABLES=" + ($actual -join ','))
    Write-Output ("MISSING_TABLES=" + ($(if ($missing) { $missing -join ',' } else { 'none' })))
    Write-Output ("EXTRA_TABLES=" + ($(if ($extra) { $extra -join ',' } else { 'none' })))

    $pk = Invoke-Psql -Database 'smt_dev' -TuplesOnly -Sql "SELECT count(*) FROM pg_constraint WHERE contype = 'p' AND connamespace = 'public'::regnamespace;"
    $fk = Invoke-Psql -Database 'smt_dev' -TuplesOnly -Sql "SELECT count(*) FROM pg_constraint WHERE contype = 'f' AND connamespace = 'public'::regnamespace;"
    $idx = Invoke-Psql -Database 'smt_dev' -TuplesOnly -Sql "SELECT count(*) FROM pg_indexes WHERE schemaname = 'public';"
    $checks = Invoke-Psql -Database 'smt_dev' -TuplesOnly -Sql "SELECT count(*) FROM pg_constraint WHERE contype = 'c' AND connamespace = 'public'::regnamespace;"
    $roles = Invoke-Psql -Database 'smt_dev' -TuplesOnly -Sql "SELECT rolname FROM pg_roles WHERE rolname LIKE 'smt\_%' ESCAPE '\' ORDER BY 1;"
    Write-Output ("PRIMARY_KEYS=" + (($pk | Out-String).Trim()))
    Write-Output ("FOREIGN_KEYS=" + (($fk | Out-String).Trim()))
    Write-Output ("INDEXES=" + (($idx | Out-String).Trim()))
    Write-Output ("CHECK_CONSTRAINTS=" + (($checks | Out-String).Trim()))
    Write-Output ("ROLES=" + (($roles | ForEach-Object { "$_".Trim() } | Where-Object { $_ }) -join ','))
    Write-Output 'SETUP_DATABASE_OK'
} catch {
    Write-Output 'SETUP_FAILED'
    Write-Output $_.Exception.Message
    exit 1
} finally {
    Clear-PgPassword
}
