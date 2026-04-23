param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$DataRoot = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")).Path "new_data"),
    [string]$Output = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")).Path "manifest.json")
)

$imageExtensions = @(".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
$projectRootPath = (Resolve-Path $ProjectRoot).Path
$dataRootPath = (Resolve-Path $DataRoot).Path

$candidateDirectories = @(
    (Get-Item -Path $dataRootPath)
    Get-ChildItem -Path $dataRootPath -Directory -Recurse | Sort-Object FullName
)

$folders = @(
    $candidateDirectories |
        ForEach-Object {
            $images = @(
                Get-ChildItem -Path $_.FullName -File |
                    Where-Object { $imageExtensions -contains $_.Extension.ToLowerInvariant() } |
                    Sort-Object Name |
                    ForEach-Object {
                        $relativePath = $_.FullName.Substring($projectRootPath.Length).TrimStart("\", "/") -replace "\\", "/"

                        [PSCustomObject]@{
                            file = $_.Name
                            path = $relativePath
                            size = $_.Length
                        }
                    }
            )

            if ($images.Count -gt 0) {
                $relativeFolder = $_.FullName.Substring($dataRootPath.Length).TrimStart("\", "/") -replace "\\", "/"
                if ([string]::IsNullOrWhiteSpace($relativeFolder)) {
                    $relativeFolder = "."
                }

                [PSCustomObject]@{
                    name = $relativeFolder
                    count = $images.Count
                    images = $images
                }
            }
        } |
        Sort-Object name
)

$totalImages = ($folders | Measure-Object -Property count -Sum).Sum
if ($null -eq $totalImages) {
    $totalImages = 0
}

$manifest = [PSCustomObject]@{
    generatedAt = (Get-Date).ToString("o")
    dataRoot = "new_data"
    totals = [PSCustomObject]@{
        folders = $folders.Count
        images = $totalImages
    }
    folders = $folders
}

$manifest |
    ConvertTo-Json -Depth 6 |
    Set-Content -Path $Output -Encoding utf8

Write-Host "Manifest written to $Output"
