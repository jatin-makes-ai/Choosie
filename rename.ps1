$files = Get-ChildItem -Path "choosie","tests","examples" -Recurse -File -Include "*.py"
foreach ($f in $files) {
    $content = Get-Content $f.FullName -Raw
    $content = $content -replace 'vibediff', 'choosie'
    $content = $content -replace 'VibeDiff', 'Choosie'
    Set-Content $f.FullName -Value $content -NoNewline
}

# pyproject.toml
$content = Get-Content "pyproject.toml" -Raw
$content = $content -replace 'vibediff', 'choosie'
$content = $content -replace 'VibeDiff', 'Choosie'
Set-Content "pyproject.toml" -Value $content -NoNewline

# README.md
$content = Get-Content "README.md" -Raw
$content = $content -replace 'vibediff', 'choosie'
$content = $content -replace 'VibeDiff', 'Choosie'
Set-Content "README.md" -Value $content -NoNewline

# .gitignore
$content = Get-Content ".gitignore" -Raw
$content = $content -replace 'vibediff', 'choosie'
$content = $content -replace 'VibeDiff', 'Choosie'
Set-Content ".gitignore" -Value $content -NoNewline

Write-Host "Done! All references renamed to choosie/Choosie."
