param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$Output = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")).Path "manifest.json")
)

$imageExtensions = @(".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
$rootPath = (Resolve-Path $Root).Path

$folders = @(
    Get-ChildItem -Path $rootPath -Directory |
        Sort-Object Name |
        ForEach-Object {
            $images = @(
                Get-ChildItem -Path $_.FullName -Recurse -File |
                    Where-Object { $imageExtensions -contains $_.Extension.ToLowerInvariant() } |
                    Sort-Object FullName |
                    ForEach-Object {
                        $relativePath = $_.FullName.Substring($rootPath.Length).TrimStart("\", "/") -replace "\\", "/"

                        [PSCustomObject]@{
                            file = $_.Name
                            path = $relativePath
                            size = $_.Length
                        }
                    }
            )

            if ($images.Count -gt 0) {
                [PSCustomObject]@{
                    name = $_.Name
                    count = $images.Count
                    images = $images
                }
            }
        }
)

$totalImages = ($folders | Measure-Object -Property count -Sum).Sum
if ($null -eq $totalImages) {
    $totalImages = 0
}

$manifest = [PSCustomObject]@{
    generatedAt = (Get-Date).ToString("o")
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
