# KeePassXC OTP Integration for Home Assistant

[English](#english) | [Deutsch](#deutsch)

---

## English

A Home Assistant custom integration that reads OTP/TOTP entries from a KeePassXC database and creates Home Assistant sensors for easy access to your two-factor authentication codes.

### Features

- 📱 **Read TOTP codes** from KeePassXC database
- 🔄 **Automatic updates** - codes refresh every 10 seconds with countdown timer
- 🔐 **Secure authentication** - supports password and keyfile authentication
- 🧹 **Auto-cleanup** - removes old sensors before each sync
- 🌍 **Multi-language** - English and German translations
- 🎨 **Home Assistant UI** - easy configuration through the UI
- 👥 **Multi-user support** - each Home Assistant user can have their own OTP database

### Multi-User Support

Each Home Assistant user can configure their own KeePassXC database with separate OTP entries:

#### How It Works

- **User-Specific Directories**: Each user gets their own directory: `/config/keepassxc_otp/user_<user_id>/`
- **Separate OTP Entries**: Users only see their own OTP tokens
- **User-Prefixed Entity IDs**: Entities are named with user prefix for easy identification
  - Example: `sensor.keepassxc_otp_alice_gmail` (Alice's Gmail OTP)
  - Example: `sensor.keepassxc_otp_bob_github` (Bob's GitHub OTP)
- **Privacy & Security**: Users cannot access other users' OTP tokens
- **Admin View**: Administrators can optionally view all users' tokens in the Lovelace card

#### Setup for Each User

1. **Log in as your user** in Home Assistant
2. **Add the integration** (Settings → Integrations → Add → KeePassXC OTP)
3. **Place your database** in `/config/keepassxc_otp/user_<your_user_id>/`
   - The directory will be created automatically when you add the integration
   - Each user has their own isolated directory
4. **Configure your database** with your password and optional keyfile

#### Entity Naming

Entities include your username for easy identification:
- Friendly name: `Gmail (Alice)`, `GitHub (Bob)`
- Entity ID: `sensor.keepassxc_otp_alice_gmail`, `sensor.keepassxc_otp_bob_github`
- Attributes include `user_id` and `user_name` for filtering and permissions

#### Lovelace Card Filtering

The custom Lovelace card automatically filters entities:
- **Users** see only their own OTP tokens
- **Admins** can see all tokens by setting `show_all_users: true`

```yaml
# Regular user view (sees only own tokens)
type: custom:keepassxc-otp-card
title: 🔐 My OTP Tokens

# Admin view (sees all users' tokens)
type: custom:keepassxc-otp-card
title: 🔐 All OTP Tokens
show_all_users: true
```

#### Permission Validation

- Config flow validates user ownership during setup and reconfiguration
- Copy service logs attempts to access other users' tokens
- Admins can manage all integrations, regular users can only manage their own

### Installation

#### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/XtraLarge/keepassxc_otp`
6. Select "Integration" as the category
7. Click "Add"
8. Search for "KeePassXC OTP" and install it
9. Restart Home Assistant

**A directory will be automatically created:** `/config/keepassxc_otp/`

#### Manual Installation

1. Copy the `custom_components/keepassxc_otp` folder to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

**A directory will be automatically created:** `/config/keepassxc_otp/`

### Configuration

#### Single User or Shared Mode (Legacy)

For backward compatibility, you can still use the shared directory:

1. **Copy your files** to `/config/keepassxc_otp/`:
   - Your KeePassXC database file (e.g., `database.kdbx`)
   - Your keyfile (optional, e.g., `keyfile.key`)

#### Multi-User Mode (Recommended)

For user-specific OTP management:

1. **Log in as your user** in Home Assistant
2. **Add the integration** (Settings → Devices & Services → Add Integration → KeePassXC OTP)
3. **Copy your files** to the user-specific directory shown in the configuration form:
   - The directory will be `/config/keepassxc_otp/user_<your_user_id>/`
   - This directory is automatically created when you start the configuration

   You can copy files via:
   - **File Editor** add-on in Home Assistant
   - **SSH** or **Terminal** add-on
   - **Samba Share** add-on
   - Any file manager with access to your Home Assistant config directory

4. **Configure the integration:**
   - **Database filename**: `database.kdbx` (or your filename)
   - **Master password**: Your KeePassXC password
   - **Keyfile filename**: `keyfile.key` (optional, or your keyfile name)

5. **Files are deleted after import** for security
   - All OTP secrets are extracted and stored encrypted in Home Assistant
   - Original files are securely deleted from the storage directory
   - To update: Use the reconfigure feature (see below)

⚠️ **Important:** Files in the storage directory will be permanently deleted after successful import!

**Note:** In multi-user mode, the configuration form shows the exact path where you should place your files.

The integration will:
- Validate your credentials
- Remove any old OTP sensors from previous syncs
- Scan your database for OTP entries
- Create a sensor for each OTP entry found

### Reconfiguration (Update OTP Entries)

If you've added, removed, or modified OTP entries in your KeePassXC database, you can update the integration:

1. **Copy updated files** to `/config/keepassxc_otp/`:
   - Your updated KeePassXC database file
   - Your keyfile (if using one)

2. **Reconfigure the integration:**
   - Go to Settings → Devices & Services
   - Find "KeePassXC OTP"
   - Click the three dots menu (⋮)
   - Click "Reconfigure"

3. **Enter the configuration:**
   - Database filename
   - Master password
   - Keyfile (optional)

4. **What happens:**
   - ✅ Old OTP entities are removed
   - ✅ New OTP entries are extracted from the database
   - ✅ New entities are created
   - ✅ Files are securely deleted
   - ✅ Entity history is preserved if entity names match

⚠️ **Note:** If entity names have changed, history will not be preserved for those entities.

### How It Works

#### Supported OTP Formats

The integration looks for OTP data in KeePassXC entries in the following locations:
1. Custom attribute named `otp`, `totp`, or `otpauth`
2. Built-in TOTP field
3. Any custom attribute containing `otpauth://` URI

#### Example KeePassXC Entry

```
Entry: "GitHub"
- Username: user@example.com
- Password: ********
- Custom Attributes:
  - otp: otpauth://totp/GitHub:user@example.com?secret=JBSWY3DPEHPK3PXP&issuer=GitHub
```

This creates sensor: `sensor.keepassxc_otp_github`

#### Sensor Attributes

Each sensor provides:
- **State**: Current 6-digit TOTP code (zero-padded)
- **Attributes**:
  - `entry_name`: Entry title from KeePassXC
  - `issuer`: Service name (e.g., "GitHub")
  - `account`: Account identifier (e.g., email)
  - `time_remaining`: Seconds until code expires
  - `period`: TOTP refresh period (usually 30 seconds)

### Usage Examples

#### Display in Lovelace

```yaml
type: entities
title: OTP Codes
entities:
  - entity: sensor.keepassxc_otp_github
    secondary_info: attribute:time_remaining
  - entity: sensor.keepassxc_otp_google
    secondary_info: attribute:time_remaining
```

#### Automation Example

```yaml
automation:
  - alias: "Notify when OTP code changes"
    trigger:
      - platform: state
        entity_id: sensor.keepassxc_otp_github
    action:
      - service: notify.mobile_app
        data:
          message: "New GitHub OTP: {{ states('sensor.keepassxc_otp_github') }}"
```

## Lovelace Card

The integration includes a custom Lovelace card with auto-discovery of all OTP entities.

### Features

- 🔍 **Auto-Discovery** - Automatically finds all KeePassXC OTP sensors
- 📋 **Copy to Clipboard** - Click button to copy token
- 🎨 **Color-Coded Gauge** - Visual timer (Green → Yellow → Red)
- 🔄 **Live Updates** - Tokens refresh automatically
- 💅 **Modern Design** - Beautiful and responsive

### Installation

The card is automatically registered when you install the integration.

### Usage

Add to your Lovelace dashboard:

```yaml
type: custom:keepassxc-otp-card
title: 🔐 My OTP Tokens
show_gauge: true
show_copy_button: true
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `title` | string | `🔐 KeePassXC OTP` | Card title |
| `show_gauge` | boolean | `true` | Show time remaining gauge |
| `show_copy_button` | boolean | `true` | Show copy button |
| `layout` | string | `auto` | Layout mode |

### Services

#### `keepassxc_otp.copy_token`

Copy an OTP token to clipboard.

```yaml
service: keepassxc_otp.copy_token
data:
  entity_id: sensor.keepassxc_otp_gmail
```

#### `keepassxc_otp.get_all_entities`

Get list of all OTP entities (used internally by card).

### Card Display

The card displays:
- Entity name and issuer
- Current 6-digit token (formatted as "123 456")
- Time remaining gauge with color coding:
  - 🟢 Green: 20-30 seconds remaining
  - 🟡 Yellow: 10-19 seconds remaining
  - 🔴 Red: 0-9 seconds remaining
- Copy button that shows "✅ Copied!" on success

### Troubleshooting

#### Integration not showing up
- Make sure you've restarted Home Assistant after installation
- Check the logs for any errors: **Settings** → **System** → **Logs**

#### "Database not found" error
- Verify the path to your database file is correct
- Ensure Home Assistant has read permissions for the file
- Use absolute paths (e.g., `/config/keepass.kdbx`)

#### "Invalid password" error
- Double-check your master password
- If using a keyfile, ensure the path is correct
- Try opening the database in KeePassXC to verify credentials

#### No sensors created
- Ensure your KeePassXC entries have OTP configured
- Check that OTP data is stored in a supported format (otpauth:// URI)
- Look at the logs for entries that couldn't be parsed

#### Sensors not updating
- Check that the integration hasn't been disabled
- Reload the integration: **Settings** → **Devices & Services** → **KeePassXC OTP** → **⋮** → **Reload**

### Security Considerations

- 🔒 Passwords are stored encrypted in Home Assistant's secure storage
- 🚫 Passwords and secrets are never logged
- 📖 Database is opened in read-only mode
- 🛡️ Input validation prevents path traversal attacks
- ⚠️ Error handling prevents crashes that could expose sensitive data

### Requirements

- Home Assistant 2023.1 or newer
- Python 3.9 or newer
- KeePassXC database (.kdbx format)
- Required Python packages (automatically installed):
  - `pykeepass>=4.0.0`
  - `pyotp>=2.8.0`

### Limitations

- Only TOTP (Time-based OTP) is currently supported, not HOTP (Counter-based OTP)
- Database must be accessible on the local filesystem
- Large databases may take a few seconds to scan

### Support

- **Issues**: [GitHub Issues](https://github.com/XtraLarge/keepassxc_otp/issues)
- **Discussions**: [GitHub Discussions](https://github.com/XtraLarge/keepassxc_otp/discussions)

### License

This project is licensed under the MIT License.

---

## Deutsch

Eine Home Assistant Custom Integration, die OTP/TOTP-Einträge aus einer KeePassXC-Datenbank liest und Home Assistant Sensoren für einen einfachen Zugriff auf Ihre Zwei-Faktor-Authentifizierungscodes erstellt.

### Funktionen

- 📱 **TOTP-Codes lesen** aus KeePassXC-Datenbank
- 🔄 **Automatische Updates** - Codes werden alle 10 Sekunden mit Countdown-Timer aktualisiert
- 🔐 **Sichere Authentifizierung** - unterstützt Passwort- und Schlüsseldatei-Authentifizierung
- 🧹 **Auto-Cleanup** - entfernt alte Sensoren vor jeder Synchronisierung
- 🌍 **Mehrsprachig** - Englische und deutsche Übersetzungen
- 🎨 **Home Assistant UI** - einfache Konfiguration über die Benutzeroberfläche
- 👥 **Mehrbenutzer-Unterstützung** - jeder Home Assistant Benutzer kann seine eigene OTP-Datenbank haben

### Mehrbenutzer-Unterstützung

Jeder Home Assistant Benutzer kann seine eigene KeePassXC-Datenbank mit separaten OTP-Einträgen konfigurieren:

#### Funktionsweise

- **Benutzerspezifische Verzeichnisse**: Jeder Benutzer erhält sein eigenes Verzeichnis: `/config/keepassxc_otp/user_<benutzer_id>/`
- **Getrennte OTP-Einträge**: Benutzer sehen nur ihre eigenen OTP-Token
- **Benutzerpräfix in Entitäts-IDs**: Entitäten werden mit Benutzerpräfix benannt zur einfachen Identifizierung
  - Beispiel: `sensor.keepassxc_otp_alice_gmail` (Alices Gmail OTP)
  - Beispiel: `sensor.keepassxc_otp_bob_github` (Bobs GitHub OTP)
- **Datenschutz & Sicherheit**: Benutzer können nicht auf OTP-Token anderer Benutzer zugreifen
- **Admin-Ansicht**: Administratoren können optional alle Benutzer-Token in der Lovelace-Karte anzeigen

#### Einrichtung für jeden Benutzer

1. **Melden Sie sich als Ihr Benutzer** in Home Assistant an
2. **Fügen Sie die Integration hinzu** (Einstellungen → Integrationen → Hinzufügen → KeePassXC OTP)
3. **Platzieren Sie Ihre Datenbank** in `/config/keepassxc_otp/user_<ihre_benutzer_id>/`
   - Das Verzeichnis wird automatisch erstellt, wenn Sie die Integration hinzufügen
   - Jeder Benutzer hat sein eigenes isoliertes Verzeichnis
4. **Konfigurieren Sie Ihre Datenbank** mit Ihrem Passwort und optionaler Schlüsseldatei

#### Entitätsbenennung

Entitäten enthalten Ihren Benutzernamen zur einfachen Identifizierung:
- Anzeigename: `Gmail (Alice)`, `GitHub (Bob)`
- Entitäts-ID: `sensor.keepassxc_otp_alice_gmail`, `sensor.keepassxc_otp_bob_github`
- Attribute enthalten `user_id` und `user_name` für Filterung und Berechtigungen

#### Lovelace-Karten-Filterung

Die benutzerdefinierte Lovelace-Karte filtert Entitäten automatisch:
- **Benutzer** sehen nur ihre eigenen OTP-Token
- **Admins** können alle Token sehen durch `show_all_users: true`

```yaml
# Normale Benutzeransicht (sieht nur eigene Token)
type: custom:keepassxc-otp-card
title: 🔐 Meine OTP-Token

# Admin-Ansicht (sieht alle Benutzer-Token)
type: custom:keepassxc-otp-card
title: 🔐 Alle OTP-Token
show_all_users: true
```

#### Berechtigungsvalidierung

- Konfigurationsablauf validiert Benutzerbesitz während Einrichtung und Neukonfiguration
- Kopierdienst protokolliert Versuche auf Token anderer Benutzer zuzugreifen
- Admins können alle Integrationen verwalten, normale Benutzer nur ihre eigenen

### Installation

#### HACS (Empfohlen)

1. Öffnen Sie HACS in Home Assistant
2. Gehen Sie zu "Integrationen"
3. Klicken Sie auf die drei Punkte in der oberen rechten Ecke
4. Wählen Sie "Benutzerdefinierte Repositories"
5. Fügen Sie diese Repository-URL hinzu: `https://github.com/XtraLarge/keepassxc_otp`
6. Wählen Sie "Integration" als Kategorie
7. Klicken Sie auf "Hinzufügen"
8. Suchen Sie nach "KeePassXC OTP" und installieren Sie es
9. Starten Sie Home Assistant neu

**Ein Verzeichnis wird automatisch erstellt:** `/config/keepassxc_otp/`

#### Manuelle Installation

1. Kopieren Sie den Ordner `custom_components/keepassxc_otp` in Ihr Home Assistant `custom_components` Verzeichnis
2. Starten Sie Home Assistant neu

**Ein Verzeichnis wird automatisch erstellt:** `/config/keepassxc_otp/`

### Konfiguration

#### Einzelbenutzer oder geteilter Modus (Legacy)

Für Rückwärtskompatibilität können Sie weiterhin das geteilte Verzeichnis verwenden:

1. **Kopieren Sie Ihre Dateien** nach `/config/keepassxc_otp/`:
   - Ihre KeePassXC-Datenbankdatei (z.B. `database.kdbx`)
   - Ihre Schlüsseldatei (optional, z.B. `keyfile.key`)

#### Mehrbenutzer-Modus (Empfohlen)

Für benutzerspezifische OTP-Verwaltung:

1. **Melden Sie sich als Ihr Benutzer** in Home Assistant an
2. **Fügen Sie die Integration hinzu** (Einstellungen → Geräte & Dienste → Integration hinzufügen → KeePassXC OTP)
3. **Kopieren Sie Ihre Dateien** in das benutzerspezifische Verzeichnis, das im Konfigurationsformular angezeigt wird:
   - Das Verzeichnis wird `/config/keepassxc_otp/user_<ihre_benutzer_id>/` sein
   - Dieses Verzeichnis wird automatisch erstellt, wenn Sie die Konfiguration starten

   Sie können Dateien kopieren über:
   - **File Editor** Add-on in Home Assistant
   - **SSH** oder **Terminal** Add-on
   - **Samba Share** Add-on
   - Jeden Dateimanager mit Zugriff auf Ihr Home Assistant Config-Verzeichnis

4. **Konfigurieren Sie die Integration:**
   - **Datenbank-Dateiname**: `database.kdbx` (oder Ihr Dateiname)
   - **Master-Passwort**: Ihr KeePassXC-Passwort
   - **Keyfile-Dateiname**: `keyfile.key` (optional, oder Ihr Keyfile-Name)

5. **Dateien werden nach dem Import gelöscht** aus Sicherheitsgründen
   - Alle OTP-Geheimnisse werden extrahiert und verschlüsselt in Home Assistant gespeichert
   - Original-Dateien werden sicher aus dem Speicherverzeichnis gelöscht
   - Zum Aktualisieren: Verwenden Sie die Neukonfigurations-Funktion (siehe unten)

⚠️ **Wichtig:** Dateien im Speicherverzeichnis werden nach erfolgreichem Import dauerhaft gelöscht!

**Hinweis:** Im Mehrbenutzer-Modus zeigt das Konfigurationsformular den genauen Pfad, wo Sie Ihre Dateien platzieren sollten.

Die Integration wird:
- Ihre Anmeldeinformationen validieren
- Alle alten OTP-Sensoren aus vorherigen Synchronisierungen entfernen
- Ihre Datenbank nach OTP-Einträgen durchsuchen
- Einen Sensor für jeden gefundenen OTP-Eintrag erstellen

### Neukonfiguration (OTP-Einträge aktualisieren)

Wenn Sie OTP-Einträge in Ihrer KeePassXC-Datenbank hinzugefügt, entfernt oder geändert haben, können Sie die Integration aktualisieren:

1. **Kopieren Sie aktualisierte Dateien** nach `/config/keepassxc_otp/`:
   - Ihre aktualisierte KeePassXC-Datenbankdatei
   - Ihre Schlüsseldatei (falls verwendet)

2. **Konfigurieren Sie die Integration neu:**
   - Gehen Sie zu Einstellungen → Geräte & Dienste
   - Finden Sie "KeePassXC OTP"
   - Klicken Sie auf das Drei-Punkte-Menü (⋮)
   - Klicken Sie auf "Neu konfigurieren"

3. **Geben Sie die Konfiguration ein:**
   - Datenbank-Dateiname
   - Master-Passwort
   - Schlüsseldatei (optional)

4. **Was passiert:**
   - ✅ Alte OTP-Entitäten werden entfernt
   - ✅ Neue OTP-Einträge werden aus der Datenbank extrahiert
   - ✅ Neue Entitäten werden erstellt
   - ✅ Dateien werden sicher gelöscht
   - ✅ Entitäts-Historie bleibt erhalten, wenn Namen übereinstimmen

⚠️ **Hinweis:** Wenn sich Entitätsnamen geändert haben, bleibt die Historie für diese Entitäten nicht erhalten.

### Funktionsweise

#### Unterstützte OTP-Formate

Die Integration sucht nach OTP-Daten in KeePassXC-Einträgen an folgenden Stellen:
1. Benutzerdefiniertes Attribut mit Namen `otp`, `totp` oder `otpauth`
2. Eingebautes TOTP-Feld
3. Jedes benutzerdefinierte Attribut, das eine `otpauth://` URI enthält

#### Beispiel KeePassXC-Eintrag

```
Eintrag: "GitHub"
- Benutzername: user@example.com
- Passwort: ********
- Benutzerdefinierte Attribute:
  - otp: otpauth://totp/GitHub:user@example.com?secret=JBSWY3DPEHPK3PXP&issuer=GitHub
```

Dies erstellt Sensor: `sensor.keepassxc_otp_github`

#### Sensor-Attribute

Jeder Sensor bietet:
- **Status**: Aktueller 6-stelliger TOTP-Code (mit Nullen aufgefüllt)
- **Attribute**:
  - `entry_name`: Eintragstitel aus KeePassXC
  - `issuer`: Dienstname (z.B. "GitHub")
  - `account`: Konto-Kennung (z.B. E-Mail)
  - `time_remaining`: Sekunden bis zum Ablauf des Codes
  - `period`: TOTP-Aktualisierungsperiode (normalerweise 30 Sekunden)

### Verwendungsbeispiele

#### Anzeige in Lovelace

```yaml
type: entities
title: OTP-Codes
entities:
  - entity: sensor.keepassxc_otp_github
    secondary_info: attribute:time_remaining
  - entity: sensor.keepassxc_otp_google
    secondary_info: attribute:time_remaining
```

#### Automatisierungsbeispiel

```yaml
automation:
  - alias: "Benachrichtigen wenn OTP-Code sich ändert"
    trigger:
      - platform: state
        entity_id: sensor.keepassxc_otp_github
    action:
      - service: notify.mobile_app
        data:
          message: "Neuer GitHub OTP: {{ states('sensor.keepassxc_otp_github') }}"
```

## Lovelace-Karte

Die Integration enthält eine benutzerdefinierte Lovelace-Karte mit automatischer Erkennung aller OTP-Entitäten.

### Funktionen

- 🔍 **Auto-Erkennung** - Findet automatisch alle KeePassXC OTP-Sensoren
- 📋 **In Zwischenablage kopieren** - Klicken Sie auf die Schaltfläche, um das Token zu kopieren
- 🎨 **Farbcodierte Anzeige** - Visueller Timer (Grün → Gelb → Rot)
- 🔄 **Live-Updates** - Token werden automatisch aktualisiert
- 💅 **Modernes Design** - Schön und responsiv

### Installation

Die Karte wird automatisch registriert, wenn Sie die Integration installieren.

### Verwendung

Fügen Sie dies zu Ihrem Lovelace-Dashboard hinzu:

```yaml
type: custom:keepassxc-otp-card
title: 🔐 Meine OTP-Token
show_gauge: true
show_copy_button: true
```

### Konfigurationsoptionen

| Option | Typ | Standard | Beschreibung |
|--------|-----|----------|--------------|
| `title` | string | `🔐 KeePassXC OTP` | Kartentitel |
| `show_gauge` | boolean | `true` | Verbleibende Zeit-Anzeige anzeigen |
| `show_copy_button` | boolean | `true` | Kopierschaltfläche anzeigen |
| `layout` | string | `auto` | Layout-Modus |

### Dienste

#### `keepassxc_otp.copy_token`

Ein OTP-Token in die Zwischenablage kopieren.

```yaml
service: keepassxc_otp.copy_token
data:
  entity_id: sensor.keepassxc_otp_gmail
```

#### `keepassxc_otp.get_all_entities`

Liste aller OTP-Entitäten abrufen (wird intern von der Karte verwendet).

### Kartenanzeige

Die Karte zeigt:
- Entitätsname und Aussteller
- Aktueller 6-stelliger Token (formatiert als "123 456")
- Verbleibende Zeit-Anzeige mit Farbcodierung:
  - 🟢 Grün: 20-30 Sekunden verbleibend
  - 🟡 Gelb: 10-19 Sekunden verbleibend
  - 🔴 Rot: 0-9 Sekunden verbleibend
- Kopierschaltfläche, die "✅ Kopiert!" bei Erfolg anzeigt

### Fehlerbehebung

#### Integration wird nicht angezeigt
- Stellen Sie sicher, dass Sie Home Assistant nach der Installation neu gestartet haben
- Überprüfen Sie die Protokolle auf Fehler: **Einstellungen** → **System** → **Protokolle**

#### Fehler "Datenbank nicht gefunden"
- Überprüfen Sie, ob der Pfad zu Ihrer Datenbankdatei korrekt ist
- Stellen Sie sicher, dass Home Assistant Leseberechtigungen für die Datei hat
- Verwenden Sie absolute Pfade (z.B. `/config/keepass.kdbx`)

#### Fehler "Ungültiges Passwort"
- Überprüfen Sie Ihr Master-Passwort
- Wenn Sie eine Schlüsseldatei verwenden, stellen Sie sicher, dass der Pfad korrekt ist
- Versuchen Sie, die Datenbank in KeePassXC zu öffnen, um die Anmeldeinformationen zu überprüfen

#### Keine Sensoren erstellt
- Stellen Sie sicher, dass Ihre KeePassXC-Einträge OTP konfiguriert haben
- Überprüfen Sie, dass OTP-Daten in einem unterstützten Format gespeichert sind (otpauth:// URI)
- Schauen Sie sich die Protokolle nach Einträgen an, die nicht geparst werden konnten

#### Sensoren werden nicht aktualisiert
- Überprüfen Sie, dass die Integration nicht deaktiviert wurde
- Laden Sie die Integration neu: **Einstellungen** → **Geräte & Dienste** → **KeePassXC OTP** → **⋮** → **Neu laden**

### Sicherheitsüberlegungen

- 🔒 Passwörter werden verschlüsselt im sicheren Speicher von Home Assistant gespeichert
- 🚫 Passwörter und Geheimnisse werden niemals protokolliert
- 📖 Datenbank wird im Nur-Lese-Modus geöffnet
- 🛡️ Eingabevalidierung verhindert Path-Traversal-Angriffe
- ⚠️ Fehlerbehandlung verhindert Abstürze, die sensible Daten offenlegen könnten

### Anforderungen

- Home Assistant 2023.1 oder neuer
- Python 3.9 oder neuer
- KeePassXC-Datenbank (.kdbx-Format)
- Erforderliche Python-Pakete (werden automatisch installiert):
  - `pykeepass>=4.0.0`
  - `pyotp>=2.8.0`

### Einschränkungen

- Derzeit wird nur TOTP (zeitbasiertes OTP) unterstützt, nicht HOTP (zählerbasiertes OTP)
- Datenbank muss im lokalen Dateisystem zugänglich sein
- Große Datenbanken können einige Sekunden zum Scannen benötigen

### Support

- **Probleme**: [GitHub Issues](https://github.com/XtraLarge/keepassxc_otp/issues)
- **Diskussionen**: [GitHub Discussions](https://github.com/XtraLarge/keepassxc_otp/discussions)

### Lizenz

Dieses Projekt ist unter der MIT-Lizenz lizenziert.