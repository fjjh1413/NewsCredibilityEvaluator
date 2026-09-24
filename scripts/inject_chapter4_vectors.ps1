param(
    [string]$MapPath = "docs/thesis/chapter4_figure_map.json"
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
function Resolve-RepositoryPath([string]$Path) {
    if (-not [System.IO.Path]::IsPathRooted($Path)) {
        $Path = Join-Path $repositoryRoot $Path
    }
    return (Resolve-Path -LiteralPath $Path).Path
}
$resolvedMap = Resolve-RepositoryPath $MapPath
$mapping = Get-Content -Raw -LiteralPath $resolvedMap -Encoding UTF8 | ConvertFrom-Json
$docxPath = Resolve-RepositoryPath ([string]$mapping.docx)

$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($docxPath)

    $pageSetup = $document.Sections.Item(1).PageSetup
    $contentWidth = $pageSetup.PageWidth - $pageSetup.LeftMargin - $pageSetup.RightMargin
    $maxHeight = 485.0
    $inserted = 0

    foreach ($figure in ($mapping.figures | Sort-Object number)) {
        $range = $document.Content
        $range.Find.ClearFormatting()
        $found = $range.Find.Execute([string]$figure.placeholder)
        if (-not $found) {
            throw "未找到图片占位符：$($figure.placeholder)"
        }

        $range.Text = ""
        $range.ParagraphFormat.Alignment = 1
        $shape = $document.InlineShapes.AddPicture(
            (Resolve-RepositoryPath ([string]$figure.path)),
            $false,
            $true,
            $range
        )
        $shape.LockAspectRatio = -1
        $targetWidth = [Math]::Min([double]$contentWidth, $maxHeight * [double]$figure.ratio)
        $shape.Width = $targetWidth
        $shape.Range.ParagraphFormat.Alignment = 1
        $inserted++
    }

    for ($index = 1; $index -le $document.TablesOfContents.Count; $index++) {
        $document.TablesOfContents.Item($index).Update()
    }
    $document.Fields.Update() | Out-Null
    $document.Save()
    Write-Output "docx=$docxPath"
    Write-Output "inserted_vectors=$inserted"
    Write-Output "toc_count=$($document.TablesOfContents.Count)"
}
finally {
    if ($null -ne $document) {
        $document.Close($false)
    }
    if ($null -ne $word) {
        $word.Quit()
    }
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
}
