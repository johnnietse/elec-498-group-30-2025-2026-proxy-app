# ============================================================================
# ELEC 498 Workspace Reorganization Script
# Transforms the flat workspace into a professional corporate structure
# ============================================================================

$root = "c:\Users\Johnnie\Documents\ELEC_498_All_directories_and_branches_folder_for_2026_02_15"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " ELEC 498 Workspace Reorganization"      -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ──────────────────────────────────────────────
# PHASE 1: Create Directory Skeleton
# ──────────────────────────────────────────────
Write-Host "`n[Phase 1] Creating directory skeleton..." -ForegroundColor Yellow

$dirs = @(
    "01_docs\reports",
    "01_docs\guides",
    "02_src\comm_phase_version",
    "02_src\mpi_comm_version",
    "02_src\controllers",
    "02_src\monitoring",
    "02_src\analysis",
    "03_scripts\batch_tests",
    "03_scripts\cluster_jobs",
    "03_scripts\setup",
    "04_configs",
    "05_data\raw_results",
    "05_data\processed",
    "05_data\synthetic",
    "05_data\misc",
    "06_outputs\final_figures",
    "06_outputs\supplementary_plots",
    "07_archive",
    "08_test_gui"
)

foreach ($d in $dirs) {
    $fullPath = Join-Path $root $d
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
        Write-Host "  Created: $d" -ForegroundColor Green
    }
}

Write-Host "[Phase 1] Done." -ForegroundColor Green

# ──────────────────────────────────────────────
# PHASE 2: Move Loose Root Files
# ──────────────────────────────────────────────
Write-Host "`n[Phase 2] Moving loose root files..." -ForegroundColor Yellow

# Reports
$reports = @("ELEC_490_Final_Report_1_converted.docx", "ELEC_490_Final_Report_2_converted.docx")
foreach ($f in $reports) {
    $src = Join-Path $root $f
    if (Test-Path $src) {
        Move-Item -Path $src -Destination (Join-Path $root "01_docs\reports\$f") -Force
        Write-Host "  Moved: $f -> 01_docs/reports/" -ForegroundColor Green
    }
}

# Raw results
$rawResults = @(
    @{ name = "results_all_24_runs.txt"; dest = "05_data\raw_results" },
    @{ name = "results_144_synthetic_runs.txt"; dest = "05_data\raw_results" },
    @{ name = "results_saved_from_running_Zane_s_setup_myself.txt"; dest = "05_data\raw_results" },
    @{ name = "zane_results_copy_from_excel_sheet.txt"; dest = "05_data\raw_results" },
    @{ name = "extracted_beta_c_runs.txt"; dest = "05_data\processed" },
    @{ name = "c2_synthetic_dataset.txt"; dest = "05_data\synthetic" },
    @{ name = "diff_results.txt"; dest = "05_data\misc" },
    @{ name = "pull_results.txt"; dest = "05_data\misc" },
    @{ name = "pull_results_2.txt"; dest = "05_data\misc" }
)

foreach ($item in $rawResults) {
    $src = Join-Path $root $item.name
    if (Test-Path $src) {
        Move-Item -Path $src -Destination (Join-Path $root "$($item.dest)\$($item.name)") -Force
        Write-Host "  Moved: $($item.name) -> $($item.dest)/" -ForegroundColor Green
    }
}

# Scripts at root
$rootScripts = @(
    @{ name = "setup_unified_run.sh"; dest = "03_scripts\cluster_jobs" }
)
foreach ($item in $rootScripts) {
    $src = Join-Path $root $item.name
    if (Test-Path $src) {
        Move-Item -Path $src -Destination (Join-Path $root "$($item.dest)\$($item.name)") -Force
        Write-Host "  Moved: $($item.name) -> $($item.dest)/" -ForegroundColor Green
    }
}

# Analysis script at root
$src = Join-Path $root "regenerate_all_plots_v4.py"
if (Test-Path $src) {
    Copy-Item -Path $src -Destination (Join-Path $root "02_src\analysis\regenerate_all_plots_v4.py") -Force
    Move-Item -Path $src -Destination (Join-Path $root "02_src\analysis\regenerate_all_plots_v4_ORIGINAL.py") -Force -ErrorAction SilentlyContinue
    # Just keep the copy
    Write-Host "  Moved: regenerate_all_plots_v4.py -> 02_src/analysis/" -ForegroundColor Green
}

Write-Host "[Phase 2] Done." -ForegroundColor Green

# ──────────────────────────────────────────────
# PHASE 3: Move Final Plots
# ──────────────────────────────────────────────
Write-Host "`n[Phase 3] Moving final plots..." -ForegroundColor Yellow

$plotsDir = Join-Path $root "final_performance_plots"
if (Test-Path $plotsDir) {
    # fig## files -> final_figures
    Get-ChildItem -Path $plotsDir -Filter "fig*" | ForEach-Object {
        Move-Item -Path $_.FullName -Destination (Join-Path $root "06_outputs\final_figures\$($_.Name)") -Force
        Write-Host "  Moved: $($_.Name) -> 06_outputs/final_figures/" -ForegroundColor Green
    }
    # plot## files -> supplementary_plots
    Get-ChildItem -Path $plotsDir -Filter "plot*" | ForEach-Object {
        Move-Item -Path $_.FullName -Destination (Join-Path $root "06_outputs\supplementary_plots\$($_.Name)") -Force
        Write-Host "  Moved: $($_.Name) -> 06_outputs/supplementary_plots/" -ForegroundColor Green
    }
    # Remove empty directory
    $remaining = Get-ChildItem -Path $plotsDir -Force
    if ($remaining.Count -eq 0) {
        Remove-Item -Path $plotsDir -Force
        Write-Host "  Removed empty: final_performance_plots/" -ForegroundColor DarkGray
    }
}

Write-Host "[Phase 3] Done." -ForegroundColor Green

# ──────────────────────────────────────────────
# PHASE 4: Move Development Branches to Archive
# ──────────────────────────────────────────────
Write-Host "`n[Phase 4] Moving development branches to 07_archive/..." -ForegroundColor Yellow

$branchMoves = @(
    @{ src = "johnnie-branch";     dest = "johnnie_serial_memory_phase" },
    @{ src = "johnnie-comm-phase"; dest = "johnnie_comm_phase" },
    @{ src = "gia-Final";          dest = "gia_final" },
    @{ src = "gia-scaling-io";     dest = "gia_scaling_io" },
    @{ src = "zane_mpi_comm";      dest = "zane_mpi_comm" },
    @{ src = "zane_prototype";     dest = "zane_prototype" },
    @{ src = "val_testing";        dest = "val_testing" },
    @{ src = "elec-498-group-30-2025-2026-proxy-app"; dest = "main_repo" }
)

foreach ($b in $branchMoves) {
    $srcPath = Join-Path $root $b.src
    $destPath = Join-Path $root "07_archive\$($b.dest)"
    if (Test-Path $srcPath) {
        Move-Item -Path $srcPath -Destination $destPath -Force
        Write-Host "  Moved: $($b.src) -> 07_archive/$($b.dest)/" -ForegroundColor Green
    }
}

Write-Host "[Phase 4] Done." -ForegroundColor Green

# ──────────────────────────────────────────────
# PHASE 5: Copy Final Source Into 02_src/
# ──────────────────────────────────────────────
Write-Host "`n[Phase 5] Copying final source code into 02_src/..." -ForegroundColor Yellow

# Comm phase version (from johnnie_comm_phase)
$commSrc = Join-Path $root "07_archive\johnnie_comm_phase"
$commFiles = @("integrate.cpp", "integrate.h", "ljs.cpp")
foreach ($f in $commFiles) {
    $src = Join-Path $commSrc $f
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination (Join-Path $root "02_src\comm_phase_version\$f") -Force
        Write-Host "  Copied: $f -> 02_src/comm_phase_version/" -ForegroundColor Green
    }
}

# MPI comm version (from zane_mpi_comm/mpi_comm)
$mpiSrc = Join-Path $root "07_archive\zane_mpi_comm\mpi_comm"
$mpiFiles = @("integrate.cpp", "integrate.h", "ljs.cpp")
foreach ($f in $mpiFiles) {
    $src = Join-Path $mpiSrc $f
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination (Join-Path $root "02_src\mpi_comm_version\$f") -Force
        Write-Host "  Copied: $f -> 02_src/mpi_comm_version/" -ForegroundColor Green
    }
}

# Controllers
$ctrlSrc = Join-Path $root "07_archive\johnnie_comm_phase"
$ctrlFiles = @("comm_freq_controller.py", "integrated_freq_controller.py")
foreach ($f in $ctrlFiles) {
    $src = Join-Path $ctrlSrc $f
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination (Join-Path $root "02_src\controllers\$f") -Force
        Write-Host "  Copied: $f -> 02_src/controllers/" -ForegroundColor Green
    }
}

# Monitoring
$monFiles = @(
    @{ src = "07_archive\gia_final\monitoring.py"; name = "monitoring.py" },
    @{ src = "07_archive\zane_mpi_comm\mpi_comm\dashboard.py"; name = "dashboard.py" },
    @{ src = "07_archive\zane_mpi_comm\mpi_comm\bridge_to_dashboard.py"; name = "bridge_to_dashboard.py" },
    @{ src = "07_archive\zane_mpi_comm\mpi_comm\mon.py"; name = "mon.py" }
)
foreach ($item in $monFiles) {
    $src = Join-Path $root $item.src
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination (Join-Path $root "02_src\monitoring\$($item.name)") -Force
        Write-Host "  Copied: $($item.name) -> 02_src/monitoring/" -ForegroundColor Green
    }
}

# Analysis scripts
$analysisFiles = @(
    @{ src = "07_archive\johnnie_comm_phase\analyze_results.py"; name = "analyze_results.py" },
    @{ src = "07_archive\johnnie_comm_phase\generate_synthetic_data.py"; name = "generate_synthetic_data.py" },
    @{ src = "07_archive\johnnie_comm_phase\filter_outliers.py"; name = "filter_outliers.py" }
)
foreach ($item in $analysisFiles) {
    $src = Join-Path $root $item.src
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination (Join-Path $root "02_src\analysis\$($item.name)") -Force
        Write-Host "  Copied: $($item.name) -> 02_src/analysis/" -ForegroundColor Green
    }
}

Write-Host "[Phase 5] Done." -ForegroundColor Green

# ──────────────────────────────────────────────
# PHASE 6: Copy Configs, Scripts, Data, GUI Tools
# ──────────────────────────────────────────────
Write-Host "`n[Phase 6] Copying configs, scripts, data, GUI tools..." -ForegroundColor Yellow

# Configs
$configSrc = Join-Path $root "07_archive\johnnie_serial_memory_phase"
$configFiles = @(
    "config_memory.cfg", "config_serial.cfg",
    "input_memory_1000.in", "input_memory_5000.in", "input_memory_10000.in",
    "input_memory_50000.in", "input_memory_100000.in", "input_memory_large.in",
    "input_serial.in"
)
foreach ($f in $configFiles) {
    $src = Join-Path $configSrc $f
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination (Join-Path $root "04_configs\$f") -Force
        Write-Host "  Copied: $f -> 04_configs/" -ForegroundColor Green
    }
}

# Batch test scripts
$batchSrc = Join-Path $root "07_archive\johnnie_comm_phase"
$batchFiles = @(
    "batch_test_a.sh", "batch_test_b.sh", "batch_test_c.sh", "batch_test_d.sh",
    "new_batch_test_a.sh", "new_batch_test_b.sh", "new_batch_test_c.sh",
    "integrated_new_batch_test_a.sh", "integrated_new_batch_test_b.sh", "integrated_new_batch_test_c.sh",
    "automated_test_b.sh", "run_freq_tests.sh"
)
foreach ($f in $batchFiles) {
    $src = Join-Path $batchSrc $f
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination (Join-Path $root "03_scripts\batch_tests\$f") -Force
        Write-Host "  Copied: $f -> 03_scripts/batch_tests/" -ForegroundColor Green
    }
}

# CSV / processed data
$csvFiles = @(
    "results_manual_test_b.csv", "results_manual_test_c.csv", "results_manual_test_c2.csv",
    "book1_dump.csv"
)
foreach ($f in $csvFiles) {
    $src = Join-Path $batchSrc $f
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination (Join-Path $root "05_data\processed\$f") -Force
        Write-Host "  Copied: $f -> 05_data/processed/" -ForegroundColor Green
    }
}

# Excel files
$excelFiles = @("Book1(Sheet1).xlsx", "Book1.xlsx")
foreach ($f in $excelFiles) {
    $src = Join-Path $batchSrc $f
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination (Join-Path $root "05_data\processed\$f") -Force
        Write-Host "  Copied: $f -> 05_data/processed/" -ForegroundColor Green
    }
}

# GUI tools
$guiFiles = @("test_gui.py", "test_gui_web.py", "test_gui_windowed.py", "verify_file_sizes.py")
foreach ($f in $guiFiles) {
    $src = Join-Path $batchSrc $f
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination (Join-Path $root "08_test_gui\$f") -Force
        Write-Host "  Copied: $f -> 08_test_gui/" -ForegroundColor Green
    }
}

# Docs / guides from comm phase
$guideSrc = Join-Path $root "07_archive\johnnie_comm_phase"
$guideFiles = @(
    @{ name = "ON_CLUSTER_TESTING_GUIDE.md"; dest = "01_docs\guides" },
    @{ name = "Manual_Commands_Guide.txt"; dest = "01_docs\guides" },
    @{ name = "Commands_to_test_things_out.txt"; dest = "01_docs\guides" },
    @{ name = "b_commands.txt"; dest = "01_docs\guides" },
    @{ name = "c_commands.txt"; dest = "01_docs\guides" },
    @{ name = "c2_commands.txt"; dest = "01_docs\guides" }
)
foreach ($item in $guideFiles) {
    $src = Join-Path $guideSrc $item.name
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination (Join-Path $root "$($item.dest)\$($item.name)") -Force
        Write-Host "  Copied: $($item.name) -> $($item.dest)/" -ForegroundColor Green
    }
}

Write-Host "[Phase 6] Done." -ForegroundColor Green

# ──────────────────────────────────────────────
# PHASE 7: Clean up the reorganize script itself
# ──────────────────────────────────────────────
Write-Host "`n[Phase 7] Cleanup..." -ForegroundColor Yellow

# Remove the original regenerate script if the copy exists
$origScript = Join-Path $root "02_src\analysis\regenerate_all_plots_v4_ORIGINAL.py"
if (Test-Path $origScript) {
    Remove-Item -Path $origScript -Force
    Write-Host "  Cleaned up duplicate script reference" -ForegroundColor DarkGray
}

Write-Host "[Phase 7] Done." -ForegroundColor Green

# ──────────────────────────────────────────────
# SUMMARY
# ──────────────────────────────────────────────
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " Reorganization Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`nNew top-level structure:" -ForegroundColor White
Get-ChildItem -Path $root -Directory | Where-Object { $_.Name -ne ".venv" } | ForEach-Object {
    $count = (Get-ChildItem -Path $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
    Write-Host ("  {0,-45} ({1} files)" -f $_.Name, $count) -ForegroundColor White
}
$rootFiles = (Get-ChildItem -Path $root -File).Count
Write-Host ("  {0,-45} ({1} files)" -f "[root-level files]", $rootFiles) -ForegroundColor White
