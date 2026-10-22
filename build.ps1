# Regenerates the whole dataset.
#   .\build.ps1                 -> compile both generators, generate 100 per captcha, validate
#   .\build.ps1 -Count 250      -> generate 250 per captcha
#   .\build.ps1 -SkipRu         -> only regenerate dataset/out
#
# Two datasets, two generators:
#   dataset/generator      -> dataset/out       the 18 upstream plugins
#   dataset/generator_ru   -> dataset/out_ru    the GalleryCaptcha catalogue families and
#                                                   the plugins identified from it
param(
    [int]$Count = 100,
    [string]$Out = "dataset\out",
    [string]$OutRu = "dataset\out_ru",
    [string]$JavaHome = $env:JAVA_HOME,
    [switch]$SkipRu
)

$ErrorActionPreference = "Stop"
# JDK 21 в PATH или переменная JAVA_HOME (см. AGENTS.md §4).
$javac = if ($JavaHome) { Join-Path $JavaHome "bin\javac.exe" } else { "javac" }
$java = if ($JavaHome) { Join-Path $JavaHome "bin\java.exe" } else { "java" }

if ($JavaHome -and -not (Test-Path $javac)) { throw "javac not found at $javac" }

# The core (Cg, Img, McUi, Gen, Stats, Validate) is shared by both generators.
$core = Get-ChildItem -File "dataset\generator\dev\captcha\*.java" | ForEach-Object { $_.FullName }

function Build-Generator {
    param(
        [string]$Src,
        [string]$Classes
    )
    $gens = Get-ChildItem -Recurse -Filter *.java $Src | ForEach-Object { $_.FullName }
    & $javac -encoding UTF-8 -d $Classes -sourcepath $Src $core $gens
    if ($LASTEXITCODE -ne 0) { throw "compile failed for $Src" }
}

function Generate {
    param(
        [string]$Classes,
        [string]$OutDir
    )
    & $java "-Djava.awt.headless=true" -cp $Classes dev.captcha.Gen $OutDir $Count
    if ($LASTEXITCODE -ne 0) { throw "generation failed for $OutDir" }
    Write-Host ""
    & $java "-Djava.awt.headless=true" -cp $Classes dev.captcha.Validate $OutDir
    if ($LASTEXITCODE -ne 0) { throw "validation failed for $OutDir" }
}

Build-Generator -Src "dataset\generator" -Classes "build\classes"
Generate -Classes "build\classes" -OutDir $Out

if (-not $SkipRu) {
    Write-Host ""
    Build-Generator -Src "dataset\generator_ru" -Classes "build\classes_ru"
    Generate -Classes "build\classes_ru" -OutDir $OutRu
}
