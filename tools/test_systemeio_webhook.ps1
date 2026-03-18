param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [string]$Event = "NEW_SALE",
  [string]$Email = "test@lgd.com",
  [int]$PricePlanId = 22222,
  [string]$Secret = ""
)

# ------------------------------------------------------------
# LGD — Systeme.io Webhook Test (HMAC SHA256 on RAW UTF-8 BYTES)
# ------------------------------------------------------------

if ([string]::IsNullOrWhiteSpace($Secret)) {
  Write-Host "ERROR: Provide -Secret (SYSTEMEIO_WEBHOOK_SECRET)" -ForegroundColor Red
  exit 1
}

# Stable JSON body string (no trailing newline)
$body = "{""customer"":{""email"":""$Email""},""pricePlan"":{""id"":$PricePlanId}}"

# Convert to UTF-8 bytes ONCE -> we sign and send the same bytes
$bytes = [System.Text.Encoding]::UTF8.GetBytes($body)

# HMAC SHA256 hex over RAW BYTES
$hmac = New-Object System.Security.Cryptography.HMACSHA256
$hmac.Key = [System.Text.Encoding]::UTF8.GetBytes($Secret)
$hashBytes = $hmac.ComputeHash($bytes)
$signature = ([BitConverter]::ToString($hashBytes) -replace "-", "").ToLower()

$url = "$BaseUrl/billing/webhook/systemeio"

Write-Host "POST $url"
Write-Host "Event: $Event"
Write-Host "Email: $Email"
Write-Host "PricePlanId: $PricePlanId"
Write-Host "Signature: $signature"
Write-Host "Body: $body"

try {
  # Use Invoke-WebRequest to control bytes + content-type exactly
  $resp = Invoke-WebRequest `
    -Method Post `
    -Uri $url `
    -Headers @{
      "X-Webhook-Event" = $Event
      "X-Webhook-Signature" = $signature
    } `
    -ContentType "application/json; charset=utf-8" `
    -Body $bytes

  Write-Host "OK HTTP $($resp.StatusCode)" -ForegroundColor Green
  $resp.Content
} catch {
  Write-Host "ERROR:" -ForegroundColor Red
  Write-Host $_.Exception.Message
  if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
    Write-Host $_.ErrorDetails.Message
  }
  exit 1
}
