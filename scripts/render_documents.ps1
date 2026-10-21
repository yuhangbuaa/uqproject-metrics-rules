param([string]$Round = 'round-1')
$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
$documentDirectory = Join-Path $projectDirectory 'deliverables\中期检查材料_20261022'
$renderDirectory = Join-Path $projectDirectory ".work\midterm\$Round"
New-Item -ItemType Directory -Path $renderDirectory -Force | Out-Null
$documentApplication = New-Object -ComObject KWPS.Application
$initialDocumentCount = $documentApplication.Documents.Count
$initialVisibility = $documentApplication.Visible
$initialAlerts = $documentApplication.DisplayAlerts
$documentApplication.Visible = $false
$documentApplication.DisplayAlerts = 0
try {
    foreach ($documentFile in Get-ChildItem -LiteralPath $documentDirectory -Filter '*.docx') {
        $document = $documentApplication.Documents.Open($documentFile.FullName, $false, $true)
        try {
            $null = $document.Fields.Update()
            $document.ExportAsFixedFormat((Join-Path $renderDirectory ($documentFile.BaseName + '.pdf')), 17)
            Write-Output $documentFile.Name
        } finally { $document.Close(0) }
    }
} finally {
    if ($initialDocumentCount -eq 0 -and $documentApplication.Documents.Count -eq 0) { $documentApplication.Quit() }
    else { $documentApplication.Visible = $initialVisibility; $documentApplication.DisplayAlerts = $initialAlerts }
}
