# Aggiornamento giornaliero della Guida Sport
# 1) scarica e normalizza il palinsesto -> site/events.json
# 2) Claude Code (headless) ripubblica events.json sullo stesso artifact
Set-Location $PSScriptRoot
$log = Join-Path $PSScriptRoot "data\aggiorna.log"
"=== $(Get-Date -Format s)" | Out-File $log -Append -Encoding utf8
python guida_sport.py 2>&1 | Out-File $log -Append -Encoding utf8
if ($LASTEXITCODE -ne 0) { "script fallito, pubblicazione saltata" | Out-File $log -Append -Encoding utf8; exit 1 }

$prompt = @'
Aggiorna i dati della Guida Sport. Leggi l'artifact https://claude.ai/artifact/5WqjU2RZWcFdnXov67Qc8V (action read),
poi ripubblicalo con action publish, url https://claude.ai/artifact/5WqjU2RZWcFdnXov67Qc8V,
file_path site/guida-sport.html e files {"events.json": "site/events.json"}. Non modificare nessun file.
'@
claude -p $prompt --allowedTools "Artifact" 2>&1 | Out-File $log -Append -Encoding utf8
