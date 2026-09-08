<#
.SYNOPSIS
    Local setup and launch verification for MoveWell AI on Windows.

.DESCRIPTION
    Installs frontend dependencies, creates the backend virtual environment,
    installs backend requirements, validates configuration, tests the MongoDB
    connection, and confirms both halves of the application start.

    Every step reports PASS, WARN or FAIL and the script continues where it
    safely can, so one run tells you everything that needs attention rather
    than stopping at the first problem.

    This script never writes a real credential. It reads backend\.env to check
    that required keys are present and plausible, and it never prints their
    values. If backend\.env is missing it copies the placeholder template and
    stops so you can fill it in yourself.

.PARAMETER SkipTests
    Skip the backend and frontend test suites. Faster, but you lose the
    strongest signal that the install actually works.

.PARAMETER Launch
    After the checks pass, start the API and the dev server in two new windows
    and probe both to confirm they respond.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\setup.ps1

    The recommended first run. The ExecutionPolicy argument applies to this one
    process only and changes nothing about your machine's configuration.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\setup.ps1 -Launch

    Set up, verify, then start both servers.
#>

[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$Launch
)

$ErrorActionPreference = 'Continue'

$Root        = $PSScriptRoot
$BackendDir  = Join-Path $Root 'backend'
$VenvDir     = Join-Path $BackendDir '.venv'
$VenvPython  = Join-Path $VenvDir 'Scripts\python.exe'
$EnvFile     = Join-Path $BackendDir '.env'
$EnvExample  = Join-Path $BackendDir '.env.example'

$script:Failures = New-Object System.Collections.ArrayList
$script:Warnings = New-Object System.Collections.ArrayList

function Write-Head {
    param([string]$Text)
    Write-Host ''
    Write-Host ('-' * 74) -ForegroundColor DarkGray
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host ('-' * 74) -ForegroundColor DarkGray
}

function Write-Pass {
    param([string]$Text)
    Write-Host '  [ OK ] ' -ForegroundColor Green -NoNewline
    Write-Host $Text
}

function Write-Warn {
    param([string]$Text)
    Write-Host '  [WARN] ' -ForegroundColor Yellow -NoNewline
    Write-Host $Text
    [void]$script:Warnings.Add($Text)
}

function Write-Fail {
    param([string]$Text)
    Write-Host '  [FAIL] ' -ForegroundColor Red -NoNewline
    Write-Host $Text
    [void]$script:Failures.Add($Text)
}

function Write-Note {
    param([string]$Text)
    Write-Host "         $Text" -ForegroundColor DarkGray
}


# ===========================================================================
# 1. Prerequisites
# ===========================================================================

Write-Head '1. Checking prerequisites'

# npm.cmd rather than npm: "npm" resolves to npm.ps1, which a restrictive
# PowerShell execution policy refuses to load. The .cmd shim is not subject to
# the script policy, so this avoids the problem instead of relaxing a setting.
$NpmCmd = $null
$npmCandidate = Get-Command 'npm.cmd' -ErrorAction SilentlyContinue

if ($npmCandidate) {
    $NpmCmd = $npmCandidate.Source
    $npmVersion = (& $NpmCmd '--version' 2>&1 | Out-String).Trim()
    Write-Pass "npm $npmVersion  ($NpmCmd)"
} else {
    Write-Fail 'npm.cmd was not found on PATH. Install Node.js LTS from https://nodejs.org and reopen this terminal.'
}

$NodeExe = Get-Command 'node' -ErrorAction SilentlyContinue

if ($NodeExe) {
    $nodeVersion = (& node '--version' 2>&1 | Out-String).Trim()
    $nodeMajor = 0
    if ($nodeVersion -match '^v(\d+)') { $nodeMajor = [int]$Matches[1] }

    if ($nodeMajor -ge 20) {
        Write-Pass "Node $nodeVersion"
    } else {
        Write-Fail "Node $nodeVersion is too old. Vite 8 requires Node 20.19+ or 22.12+."
    }
} else {
    Write-Fail 'node was not found on PATH. Install Node.js LTS from https://nodejs.org.'
}

# Prefer the py launcher, which is the reliable way to pick an interpreter on
# Windows, and fall back to whatever "python" resolves to.
$PyExe  = $null
$PyArgs = @()

if (Get-Command 'py' -ErrorAction SilentlyContinue) {
    $PyExe  = 'py'
    $PyArgs = @('-3')
} elseif (Get-Command 'python' -ErrorAction SilentlyContinue) {
    $PyExe  = 'python'
    $PyArgs = @()
}

if ($PyExe) {
    $pyVersion = (& $PyExe @PyArgs '-c' 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>&1 | Out-String).Trim()
    Write-Pass "Python $pyVersion  ($PyExe $($PyArgs -join ' '))"

    $pyParts = $pyVersion.Split('.')
    if ($pyParts.Count -ge 2) {
        $pyMajor = [int]$pyParts[0]
        $pyMinor = [int]$pyParts[1]

        if ($pyMajor -eq 3 -and $pyMinor -lt 9) {
            Write-Fail "Python $pyVersion is too old. Use Python 3.11 or 3.12."
        } elseif ($pyMajor -eq 3 -and $pyMinor -ge 13) {
            Write-Warn "Python $pyVersion is newer than the pinned dependencies were built against."
            Write-Note 'If pip fails to build a wheel below, install Python 3.12 and rerun.'
        }
    }
} else {
    Write-Fail 'No Python interpreter found. Install Python 3.12 from https://python.org and tick "Add python.exe to PATH".'
}

if ($script:Failures.Count -gt 0) {
    Write-Host ''
    Write-Host '  Cannot continue until the failures above are resolved.' -ForegroundColor Red
    exit 1
}


# ===========================================================================
# 2. Frontend dependencies
# ===========================================================================

Write-Head '2. Installing frontend dependencies (npm)'

Push-Location $Root
try {
    # Idempotent: with node_modules already complete this is close to a no-op,
    # and it repairs node_modules\.bin if that is missing, which is what causes
    # "vite is not recognized" when npm run dev is tried.
    Write-Note "running: $NpmCmd install"
    & $NpmCmd 'install' 2>&1 | ForEach-Object { Write-Host "         $_" -ForegroundColor DarkGray }

    if ($LASTEXITCODE -eq 0) {
        Write-Pass 'npm install completed'
    } else {
        Write-Fail "npm install exited with code $LASTEXITCODE (see output above)"
    }

    $viteShim = Join-Path $Root 'node_modules\.bin\vite.cmd'
    if (Test-Path $viteShim) {
        Write-Pass 'node_modules\.bin\vite.cmd present, so npm run dev can resolve vite'
    } else {
        Write-Fail 'node_modules\.bin\vite.cmd is still missing after install.'
        Write-Note 'Try: rmdir /s /q node_modules  then  npm install'
    }
} finally {
    Pop-Location
}


# ===========================================================================
# 3. Backend virtual environment
# ===========================================================================

Write-Head '3. Creating the backend virtual environment'

if (Test-Path $VenvPython) {
    Write-Pass "Virtual environment already exists at backend\.venv"
} else {
    Write-Note "running: $PyExe $($PyArgs -join ' ') -m venv `"$VenvDir`""
    & $PyExe @PyArgs '-m' 'venv' $VenvDir 2>&1 | ForEach-Object { Write-Host "         $_" -ForegroundColor DarkGray }

    if (Test-Path $VenvPython) {
        Write-Pass 'Virtual environment created at backend\.venv'
    } else {
        Write-Fail 'Could not create the virtual environment. See the output above.'
        Write-Host ''
        Write-Host '  Cannot continue without a virtual environment.' -ForegroundColor Red
        exit 1
    }
}


# ===========================================================================
# 4. Backend requirements
# ===========================================================================

Write-Head '4. Installing backend requirements (pip)'

Write-Note "running: python -m pip install --upgrade pip"
& $VenvPython '-m' 'pip' 'install' '--upgrade' 'pip' '--quiet' 2>&1 |
    ForEach-Object { Write-Host "         $_" -ForegroundColor DarkGray }

Write-Note "running: python -m pip install -r backend\requirements.txt"
& $VenvPython '-m' 'pip' 'install' '-r' (Join-Path $BackendDir 'requirements.txt') 2>&1 |
    ForEach-Object { Write-Host "         $_" -ForegroundColor DarkGray }

if ($LASTEXITCODE -eq 0) {
    Write-Pass 'Backend requirements installed'
} else {
    Write-Fail "pip install exited with code $LASTEXITCODE (see output above)"
}


# ===========================================================================
# 5. Configuration
# ===========================================================================

Write-Head '5. Checking backend configuration'

if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Copy-Item $EnvExample $EnvFile
        Write-Warn 'backend\.env did not exist, so the placeholder template was copied there.'
        Write-Note 'Open backend\.env and set MONGODB_URI and JWT_SECRET, then rerun this script.'
        Write-Note 'The template contains placeholders only. No real credential was written.'
        Write-Host ''
        exit 1
    }

    Write-Fail 'Neither backend\.env nor backend\.env.example exists.'
    exit 1
}

Write-Pass 'backend\.env exists'

# Key names and value lengths only. Values are never printed.
$envLines = Get-Content $EnvFile
$envMap = @{}

foreach ($line in $envLines) {
    $trimmed = $line.Trim()
    if ($trimmed -eq '' -or $trimmed.StartsWith('#')) { continue }
    $split = $trimmed.IndexOf('=')
    if ($split -lt 1) { continue }
    $key = $trimmed.Substring(0, $split).Trim()
    $value = $trimmed.Substring($split + 1).Trim()
    $envMap[$key] = $value
}

$mongoUri = $envMap['MONGODB_URI']
if (-not $mongoUri) { $mongoUri = $envMap['MONGO_URL'] }

if (-not $mongoUri) {
    Write-Fail 'MONGODB_URI is not set in backend\.env.'
} elseif ($mongoUri -like 'mongodb+srv://*') {
    Write-Pass 'MONGODB_URI is a MongoDB Atlas (mongodb+srv) connection string'

    if ($mongoUri -like '*<*' -or $mongoUri -like '*USERNAME*' -or $mongoUri -like '*PASSWORD*') {
        Write-Fail 'MONGODB_URI still contains placeholder text rather than real Atlas credentials.'
    }
} elseif ($mongoUri -like 'mongodb://localhost*' -or $mongoUri -like 'mongodb://127.0.0.1*') {
    Write-Warn 'MONGODB_URI still points at a local MongoDB, not Atlas.'
    Write-Note 'To use Atlas, replace the MONGODB_URI line in backend\.env with your'
    Write-Note 'mongodb+srv://... string from Atlas > Connect > Drivers, URL-encoding'
    Write-Note 'any special characters in the password.'
} else {
    Write-Pass 'MONGODB_URI is set'
}

$jwtSecret = $envMap['JWT_SECRET']

if (-not $jwtSecret) {
    Write-Fail 'JWT_SECRET is not set in backend\.env.'
} elseif ($jwtSecret -like 'replace-me*') {
    Write-Fail 'JWT_SECRET is still the placeholder from the template.'
    Write-Note 'Generate one:  python -c "import secrets; print(secrets.token_urlsafe(48))"'
} elseif ($jwtSecret.Length -lt 32) {
    Write-Fail "JWT_SECRET is $($jwtSecret.Length) characters. The backend requires at least 32."
} else {
    Write-Pass "JWT_SECRET is set ($($jwtSecret.Length) characters)"
}

if ($envMap.ContainsKey('OPENROUTER_API_KEY') -and $envMap['OPENROUTER_API_KEY']) {
    Write-Pass 'OPENROUTER_API_KEY is set, so report reading and guidance are enabled'

    $aiModel = $envMap['OPENROUTER_MODEL']

    if ($aiModel) {
        Write-Note "Model: $aiModel"
    } else {
        Write-Note 'OPENROUTER_MODEL is not set, so the backend default is used.'
    }
} else {
    Write-Warn 'OPENROUTER_API_KEY is not set. This is a supported configuration.'
    Write-Note 'Report reading and AI guidance will report themselves unavailable and offer'
    Write-Note 'manual entry. Everything else works. Add a key later to enable them.'

    if ($envMap.ContainsKey('ANTHROPIC_API_KEY') -and $envMap['ANTHROPIC_API_KEY']) {
        Write-Note 'ANTHROPIC_API_KEY is set, but this build calls OpenRouter instead.'
        Write-Note 'Set OPENROUTER_API_KEY in backend\.env. Get a key at openrouter.ai/keys.'
    }
}


# ===========================================================================
# 6. Preflight: config import, MongoDB connection, app assembly
# ===========================================================================

Write-Head '6. Verifying configuration, database and app assembly'

$preflightSource = @'
"""Preflight checks run inside the backend virtual environment."""

import sys
import traceback

failures = []


def redact(uri):
    """Show enough of a URI to identify it, never the credentials."""
    if "@" in uri:
        scheme, _, rest = uri.partition("://")
        host = rest.split("@", 1)[1]
        return "%s://***:***@%s" % (scheme, host)
    return uri


# --- configuration ---------------------------------------------------------

try:
    import config
except Exception as exc:
    print("[FAIL] backend configuration is not usable:")
    for line in str(exc).splitlines():
        print("       %s" % line)
    sys.exit(1)

print("[ OK ] config imported")
print("       database name: %s" % config.MONGODB_DB_NAME)
print("       connection:    %s" % redact(config.MONGODB_URI))
print("       token expiry:  %s minutes" % config.JWT_EXPIRES_MINUTES)
print("       CORS origins:  %s" % ", ".join(config.CORS_ORIGINS))
print("       AI provider:   %s" % ("available" if config.ai_provider_available() else "not configured"))

# --- dnspython, required for Atlas ----------------------------------------

if config.MONGODB_URI.startswith("mongodb+srv://"):
    try:
        import dns.resolver  # noqa: F401
        print("[ OK ] dnspython present, required to resolve a mongodb+srv:// URI")
    except ImportError:
        failures.append("dnspython is missing")
        print("[FAIL] dnspython is not installed, so an Atlas mongodb+srv:// URI cannot resolve.")
        print("       Fix: pip install \"pymongo[srv]==4.10.1\"")

# --- live database connection ---------------------------------------------

# The exception classes are imported before the connection attempt, not inside
# it. Importing them in the same try block means that if pymongo is missing the
# except clauses reference undefined names and the real problem is buried under
# a NameError.
pymongo_available = True

try:
    from pymongo import MongoClient
    from pymongo.errors import (
        ConfigurationError,
        OperationFailure,
        ServerSelectionTimeoutError,
    )
except ImportError as exc:
    pymongo_available = False
    failures.append("pymongo is not installed")
    print("[FAIL] pymongo is not installed in this environment: %s" % exc)
    print("       Fix: backend\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt")

if pymongo_available:
    try:
        client = MongoClient(config.MONGODB_URI, serverSelectionTimeoutMS=8000)
        client.admin.command("ping")
        server_info = client.server_info()
        print("[ OK ] connected to MongoDB (server version %s)" % server_info.get("version", "unknown"))

        names = client[config.MONGODB_DB_NAME].list_collection_names()
        if names:
            print("       existing collections: %s" % ", ".join(sorted(names)))
        else:
            print("       database is empty, which is expected before first use")

    except ConfigurationError as exc:
        failures.append("MongoDB configuration error")
        print("[FAIL] MongoDB connection string was rejected: %s" % exc)
        print("       For Atlas this usually means dnspython is missing.")

    except OperationFailure as exc:
        failures.append("MongoDB authentication failed")
        print("[FAIL] MongoDB refused the credentials: %s" % exc)
        print("       Check the username and password in MONGODB_URI. A password with")
        print("       special characters must be URL-encoded, and the database user needs")
        print("       readWrite on the target database.")

    except ServerSelectionTimeoutError as exc:
        failures.append("MongoDB unreachable")
        print("[FAIL] Could not reach MongoDB within 8 seconds.")
        print("       For Atlas, the usual cause is the IP access list: open Atlas >")
        print("       Network Access and add your current IP address. Also confirm the")
        print("       cluster is not paused.")
        print("       Detail: %s" % str(exc).split(",")[0])

    except Exception as exc:
        failures.append("MongoDB connection failed")
        print("[FAIL] Unexpected error connecting to MongoDB: %s: %s" % (type(exc).__name__, exc))
        traceback.print_exc()

# --- application assembly -------------------------------------------------

try:
    import main

    routes = [r for r in main.app.routes if getattr(r, "methods", None)]
    print("[ OK ] FastAPI app assembled with %d routes" % len(routes))

    expected = [
        "/api/auth/signup",
        "/api/auth/signin",
        "/api/auth/me",
        "/api/profile/complete",
        "/api/assessments",
        "/api/reports",
        "/api/guidance/run",
    ]
    missing = [path for path in expected if not any(r.path == path for r in routes)]

    if missing:
        failures.append("routes missing")
        print("[FAIL] expected routes are missing: %s" % ", ".join(missing))
    else:
        print("[ OK ] all spot-checked routes are mounted")

except Exception as exc:
    failures.append("app import failed")
    print("[FAIL] could not import the FastAPI app: %s: %s" % (type(exc).__name__, exc))
    traceback.print_exc()

sys.exit(1 if failures else 0)
'@

$preflightPath = Join-Path $env:TEMP 'movewell_preflight.py'
Set-Content -Path $preflightPath -Value $preflightSource -Encoding ASCII

Push-Location $BackendDir
try {
    & $VenvPython $preflightPath 2>&1 | ForEach-Object {
        $line = [string]$_
        if ($line -like '`[FAIL`]*') {
            Write-Host "  $line" -ForegroundColor Red
        } elseif ($line -like '`[ OK `]*') {
            Write-Host "  $line" -ForegroundColor Green
        } else {
            Write-Host "  $line" -ForegroundColor DarkGray
        }
    }

    if ($LASTEXITCODE -ne 0) {
        [void]$script:Failures.Add('Preflight checks reported problems (see section 6).')
    }
} finally {
    Pop-Location
    Remove-Item $preflightPath -ErrorAction SilentlyContinue
}


# ===========================================================================
# 7. Test suites
# ===========================================================================

if ($SkipTests) {
    Write-Head '7. Test suites (skipped by -SkipTests)'
} else {
    Write-Head '7. Running the test suites'

    Push-Location $BackendDir
    try {
        Write-Note 'running: python -m unittest discover -s tests -t .'
        $backendOutput = & $VenvPython '-m' 'unittest' 'discover' '-s' 'tests' '-t' '.' 2>&1 | Out-String
        $backendTail = ($backendOutput -split "`n" | Where-Object { $_.Trim() -ne '' } | Select-Object -Last 3) -join ' | '

        if ($LASTEXITCODE -eq 0) {
            Write-Pass "Backend tests passed  ($backendTail)"
        } else {
            Write-Fail "Backend tests failed  ($backendTail)"
            Write-Note 'Rerun for detail: backend\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v'
        }
    } finally {
        Pop-Location
    }

    Push-Location $Root
    try {
        Write-Note "running: $NpmCmd test"
        $frontendOutput = & $NpmCmd 'test' 2>&1 | Out-String
        $passLine = ($frontendOutput -split "`n" | Where-Object { $_ -match '^# (pass|fail) ' }) -join ' | '

        if ($LASTEXITCODE -eq 0) {
            Write-Pass "Frontend tests passed  ($passLine)"
        } else {
            Write-Fail "Frontend tests failed  ($passLine)"
        }
    } finally {
        Pop-Location
    }
}


# ===========================================================================
# 8. Summary and launch
# ===========================================================================

Write-Head 'Summary'

if ($script:Failures.Count -eq 0) {
    Write-Host '  Setup is complete and verified.' -ForegroundColor Green
} else {
    Write-Host "  $($script:Failures.Count) problem(s) need attention:" -ForegroundColor Red
    foreach ($failure in $script:Failures) {
        Write-Host "    - $failure" -ForegroundColor Red
    }
}

if ($script:Warnings.Count -gt 0) {
    Write-Host ''
    Write-Host "  $($script:Warnings.Count) warning(s):" -ForegroundColor Yellow
    foreach ($warning in $script:Warnings) {
        Write-Host "    - $warning" -ForegroundColor Yellow
    }
}

Write-Host ''
Write-Host '  To run the application, use two terminals:' -ForegroundColor Cyan
Write-Host ''
Write-Host '    Terminal 1 (API):        cd backend'
Write-Host '                             .venv\Scripts\Activate.ps1'
Write-Host '                             uvicorn main:app --reload --port 8000'
Write-Host ''
Write-Host '    Terminal 2 (frontend):   npm.cmd run dev'
Write-Host ''
Write-Host '    Then open http://localhost:5173'
Write-Host '    API documentation is at http://localhost:8000/docs'
Write-Host ''

if ($Launch) {
    if ($script:Failures.Count -gt 0) {
        Write-Host '  Not launching, because checks failed. Fix the problems above first.' -ForegroundColor Red
        exit 1
    }

    Write-Head 'Launching both servers'

    Start-Process -FilePath $VenvPython `
        -ArgumentList '-m', 'uvicorn', 'main:app', '--reload', '--port', '8000' `
        -WorkingDirectory $BackendDir
    Write-Pass 'API starting in a new window on port 8000'

    Start-Process -FilePath 'cmd.exe' `
        -ArgumentList '/c', 'npm.cmd run dev' `
        -WorkingDirectory $Root
    Write-Pass 'Dev server starting in a new window on port 5173'

    Write-Note 'Waiting up to 40 seconds for both to respond...'

    $apiUp = $false
    $webUp = $false

    foreach ($attempt in 1..20) {
        Start-Sleep -Seconds 2

        if (-not $apiUp) {
            try {
                $response = Invoke-WebRequest -Uri 'http://localhost:8000/' -UseBasicParsing -TimeoutSec 3
                if ($response.StatusCode -eq 200) {
                    $apiUp = $true
                    Write-Pass "API responded: $($response.Content)"
                }
            } catch { }
        }

        if (-not $webUp) {
            try {
                $response = Invoke-WebRequest -Uri 'http://localhost:5173/' -UseBasicParsing -TimeoutSec 3
                if ($response.StatusCode -eq 200) {
                    $webUp = $true
                    Write-Pass 'Dev server responded on http://localhost:5173'
                }
            } catch { }
        }

        if ($apiUp -and $webUp) { break }
    }

    if (-not $apiUp) { Write-Fail 'API did not respond on port 8000. Check its window for a traceback.' }
    if (-not $webUp) { Write-Fail 'Dev server did not respond on port 5173. Check its window for an error.' }

    if ($apiUp -and $webUp) {
        Write-Host ''
        Write-Host '  Both servers are up. Open http://localhost:5173' -ForegroundColor Green
    }
}

Write-Host ''
exit ([int]($script:Failures.Count -gt 0))
