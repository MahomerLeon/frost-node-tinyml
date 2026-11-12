// Example of secrets.h. Only needed when USE_WIFI_NTP is 1 in config.h.
//
// 1. Copy this file and name the copy secrets.h (same folder).
// 2. Write your Wi-Fi name and password in secrets.h.
// 3. Never commit secrets.h: it is listed in .gitignore.

#pragma once

const char WIFI_SSID[] = "your-wifi-name";
const char WIFI_PASSWORD[] = "your-wifi-password";
