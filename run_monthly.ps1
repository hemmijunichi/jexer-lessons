# Windows のタスクスケジューラから毎月実行する。
# 最新を取り込み -> 今月分・翌月分を取得 -> data/ に変更があれば GitHub に push。
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = 'utf-8'
Start-Transcript -Path (Join-Path $PSScriptRoot 'run.log') -Append | Out-Null
try {
    git pull --quiet
    python -m pip install --quiet --disable-pip-version-check -r requirements.txt
    python scrape.py
    if ($LASTEXITCODE -ne 0) { throw "scrape.py failed ($LASTEXITCODE)" }
    python scrape.py --next
    git add data/
    git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        git commit --quiet -m "data: $(Get-Date -Format yyyy-MM-dd) 更新"
        git push --quiet
    } else {
        'data に変更なし'
    }
} finally {
    Stop-Transcript | Out-Null
}
