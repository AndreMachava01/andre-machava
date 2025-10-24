#!/usr/bin/env pwsh
# Verificacao Profissional Completa de Codigo Antigo de Filtros

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "   VERIFICACAO PROFISSIONAL DE CODIGO ANTIGO DE FILTROS" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verificar CSS antigo em templates
Write-Host "[1] Verificando CSS antigo em templates HTML..." -ForegroundColor Yellow
$cssPatterns = @(
    "\.filter-group\s*\{",
    "\.filters-title\s*\{", 
    "\.filter-form\s*\{",
    "\.filters-grid\s*\{",
    "\.filter-label\s*\{",
    "\.filters-row\s*\{",
    "\.filters-card\s*\{",
    "\.filter-row\s*\{",
    "\.filters-container\s*\{",
    "\.filter-actions\s*\{"
)

$cssIssues = @()
Get-ChildItem templates -Recurse -Filter "*.html" | Where-Object { 
    $_.FullName -notlike "*\includes\filters_unified.html" -and 
    $_.FullName -notlike "*\examples\*" -and 
    $_.Name -notlike "base_*" 
} | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    foreach ($pattern in $cssPatterns) {
        if ($content -match $pattern) {
            $cssIssues += @{File=$_.FullName; Pattern=$pattern}
        }
    }
}

if ($cssIssues.Count -eq 0) {
    Write-Host "    [OK] Nenhum CSS antigo encontrado" -ForegroundColor Green
} else {
    Write-Host "    [ERRO] CSS antigo encontrado em $($cssIssues.Count) ocorrencias:" -ForegroundColor Red
    $cssIssues | ForEach-Object { Write-Host "      - $($_.File)" -ForegroundColor Red }
}
Write-Host ""

# 2. Verificar HTML antigo com classes de filtros
Write-Host "[2] Verificando HTML antigo com classes de filtros..." -ForegroundColor Yellow
$htmlClassIssues = @()
Get-ChildItem templates -Recurse -Filter "*.html" | Where-Object { 
    $_.FullName -notlike "*\includes\filters_unified.html" -and 
    $_.FullName -notlike "*\examples\*" -and 
    $_.Name -notlike "base_*" 
} | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    if ($content -match 'class="filters-card"' -or 
        $content -match 'class="filters-container"' -or
        $content -match 'class="filters-section"') {
        $htmlClassIssues += $_.FullName
    }
}

if ($htmlClassIssues.Count -eq 0) {
    Write-Host "    [OK] Nenhuma classe HTML antiga encontrada" -ForegroundColor Green
} else {
    Write-Host "    [ERRO] Classes HTML antigas encontradas em:" -ForegroundColor Red
    $htmlClassIssues | ForEach-Object { Write-Host "      - $_" -ForegroundColor Red }
}
Write-Host ""

# 3. Verificar formularios antigos de filtros
Write-Host "[3] Verificando formularios antigos de filtros..." -ForegroundColor Yellow
$formIssues = @()
Get-ChildItem templates -Recurse -Filter "*.html" | Where-Object { 
    $_.FullName -notlike "*\includes\filters_unified.html" -and 
    $_.FullName -notlike "*\examples\*" -and 
    $_.Name -notlike "base_*" 
} | ForEach-Object {
    $lines = Get-Content $_.FullName
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "<!-- Filtros -->|<!-- Filters -->") {
            $nextLines = $lines[($i+1)..([Math]::Min($i+50, $lines.Count-1))] -join " "
            if ($nextLines -notmatch "filters_unified") {
                $hasForm = $false
                for ($j = $i+1; $j -lt [Math]::Min($i+30, $lines.Count); $j++) {
                    if ($lines[$j] -match "<form") {
                        $hasForm = $true
                        break
                    }
                }
                if ($hasForm) {
                    $formIssues += @{File=$_.FullName; Line=$i+1}
                    break
                }
            }
        }
    }
}

if ($formIssues.Count -eq 0) {
    Write-Host "    [OK] Nenhum formulario antigo encontrado" -ForegroundColor Green
} else {
    Write-Host "    [ERRO] Formularios antigos encontrados em:" -ForegroundColor Red
    $formIssues | ForEach-Object { Write-Host "      - $($_.File):$($_.Line)" -ForegroundColor Red }
}
Write-Host ""

# 4. Verificar CSS em arquivos estaticos
Write-Host "[4] Verificando CSS antigo em arquivos estaticos..." -ForegroundColor Yellow
$staticCssIssues = @()
Get-ChildItem -Recurse -Filter "*.css" | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    foreach ($pattern in $cssPatterns) {
        if ($content -match $pattern) {
            $staticCssIssues += @{File=$_.FullName; Pattern=$pattern}
        }
    }
}

if ($staticCssIssues.Count -eq 0) {
    Write-Host "    [OK] Nenhum CSS antigo em arquivos estaticos" -ForegroundColor Green
} else {
    Write-Host "    [ERRO] CSS antigo encontrado em arquivos estaticos:" -ForegroundColor Red
    $staticCssIssues | ForEach-Object { Write-Host "      - $($_.File)" -ForegroundColor Red }
}
Write-Host ""

# Resumo Final
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "                       RESUMO FINAL" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan
$totalIssues = $cssIssues.Count + $htmlClassIssues.Count + $formIssues.Count + $staticCssIssues.Count
Write-Host "Total de problemas encontrados: $totalIssues" -ForegroundColor $(if ($totalIssues -eq 0) { "Green" } else { "Red" })
Write-Host "  - CSS antigo em templates: $($cssIssues.Count)" -ForegroundColor $(if ($cssIssues.Count -eq 0) { "Green" } else { "Red" })
Write-Host "  - Classes HTML antigas: $($htmlClassIssues.Count)" -ForegroundColor $(if ($htmlClassIssues.Count -eq 0) { "Green" } else { "Red" })
Write-Host "  - Formularios antigos: $($formIssues.Count)" -ForegroundColor $(if ($formIssues.Count -eq 0) { "Green" } else { "Red" })
Write-Host "  - CSS em arquivos estaticos: $($staticCssIssues.Count)" -ForegroundColor $(if ($staticCssIssues.Count -eq 0) { "Green" } else { "Red" })
Write-Host ""

if ($totalIssues -eq 0) {
    Write-Host "[SUCESSO] Todos os codigos antigos de filtros foram removidos!" -ForegroundColor Green
} else {
    Write-Host "[ATENCAO] Ainda existem $totalIssues problemas que precisam ser corrigidos." -ForegroundColor Red
}
Write-Host "==================================================================" -ForegroundColor Cyan

