param([string[]]$Queries)
$ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0'
foreach ($q in $Queries) {
    Write-Output "########## $q"
    $url = 'https://sourcegraph.com/.api/search/stream?q=' + [uri]::EscapeDataString($q) + '&v=V3&t=literal&display=30'
    try {
        $r = Invoke-WebRequest -Uri $url -Headers @{'User-Agent'=$ua; 'Accept'='text/event-stream'} -UseBasicParsing -TimeoutSec 90
        $lines = $r.Content -split "`n"
        $show = $false
        foreach ($l in $lines) {
            if ($l -like 'data: *') {
                $d = $l.Substring(6)
                if ($d.StartsWith('[{') -or $d.StartsWith('{"')) {
                    try { $j = $d | ConvertFrom-Json } catch { continue }
                    if ($j -is [array]) {
                        foreach ($it in $j) {
                            if ($it.type -eq 'content') {
                                $lm = $it.lineMatches | Select-Object -First 3
                                foreach ($m in $lm) { "  {0} :: {1}" -f $it.repository, $m.preview.Trim() }
                                "     path={0}" -f $it.path
                            }
                        }
                    }
                }
            }
            if ($l -like '*matchCount*') { }
        }
    } catch { "ERR $($_.Exception.Message)" }
}
