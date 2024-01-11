# PowerShell Script to Read Windows Proxy Configuration

# Define the registry path
$regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"

# Read proxy enable flag (0 = disabled, 1 = enabled)
$proxyEnable = Get-ItemProperty -Path $regPath -Name ProxyEnable

# Read proxy server details
$proxyServer = Get-ItemProperty -Path $regPath -Name ProxyServer

# Check if the proxy is enabled
if ($proxyEnable.ProxyEnable -eq 1) {
    # Extract HTTP proxy if available
    if ($proxyServer.ProxyServer -match "http=([^;]+)") {
        $httpProxy = $matches[1]
        Write-Host "HTTP Proxy Detected: $httpProxy"

        # Set HTTP_PROXY environment variable
        [Environment]::SetEnvironmentVariable("HTTP_PROXY", $httpProxy, [EnvironmentVariableTarget]::Process)

        # Additional script actions, like modifying Maven settings.xml, can go here
    } else {
        Write-Host "No HTTP proxy configuration found."
    }
} else {
    Write-Host "Proxy is disabled."
}

# Note: This script sets the environment variable for the current process.
# To make it system-wide or user-wide, you would need to change EnvironmentVariableTarget.
