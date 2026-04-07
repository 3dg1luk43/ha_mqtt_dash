# Supported devices

The app is distributed as Debian packages. Choose the variant that matches your device and iOS version. When in doubt, use the Universal package.

## Legacy — 32-bit (armv7, iOS 5.1.1 through 10.3.x)

These are the devices the project was built for. They cannot run the HA companion app, do not support modern TLS ciphers, and have no other dashboard option — MQTTDash was designed specifically for them.

| Device | Maximum iOS |
|--------|------------|
| iPad 1st gen | 5.1.1 |
| iPad 2 | 9.3.5 |
| iPad 3rd gen | 9.3.6 |
| iPad 4th gen | 10.3.3 |
| iPad mini 1st gen | 9.3.5 |

Use the **Legacy (armv7)** package for all of these.

## Modern — 64-bit (arm64, iOS 12.0 or later)

| Device family | Notes |
|--------------|-------|
| iPad Air 1st gen, iPad Air 2 | |
| iPad mini 2, mini 3, mini 4 | |
| iPad 5th gen (2017), 6th gen (2018) | |
| iPad Pro 9.7", 10.5", 12.9" (1st/2nd gen) | |

Use the **Modern (arm64)** package for these. iOS 12 or later required.

## Universal

Contains both armv7 and arm64 slices. The system installs the appropriate binary automatically. Use this if you are unsure or if you want one package that works across multiple device generations.

## Notes

- The app requires a jailbroken device and is distributed via Cydia/Sileo as a `.deb`.
- The HA integration and profile editor work in any browser and do not require jailbreak.
- iOS versions between 10.3.x and 12.0 (e.g., iPad 5th gen running iOS 11) are not currently supported — the legacy build targets armv7 devices that max out before iOS 11, and the modern build requires iOS 12.
