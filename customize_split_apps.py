from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
app = root / "app"
main = app / "src/main/java/com/example/MainActivity.kt"
admin = app / "src/main/java/com/example/admin/AdminMainActivity.kt"
manifest = app / "src/main/AndroidManifest.xml"
gradle = app / "build.gradle.kts"

s = main.read_text()
s = s.replace('    CONTROLLER("Admin", Icons.Default.ControlCamera),\n', "")
start = s.find("                    // Switch to Admin App Button")
if start >= 0:
    end = s.find("                    // Quick Siren Button in Top Bar", start)
    if end < 0:
        raise SystemExit("Could not find client top-bar button end marker")
    s = s[:start] + s[end:]
s = s.replace("                MainNavTab.CONTROLLER -> AdminControllerScreen()\n", "")
s = s.replace("import androidx.compose.material.icons.filled.AdminPanelSettings\n", "")
s = s.replace("import androidx.compose.material.icons.filled.ControlCamera\n", "")
s = s.replace("import com.example.ui.screens.AdminControllerScreen\n", "")
main.write_text(s)

s = admin.read_text()
s = s.replace("import android.content.Intent\n", "")
s = s.replace("import androidx.compose.material.icons.filled.PhoneAndroid\n", "")
s = s.replace("import androidx.compose.material3.OutlinedButton\n", "")
s = s.replace("import com.example.MainActivity\n", "")
s = s.replace("""                AdminAppRoot(
                    onOpenClientApp = {
                        val intent = Intent(this, MainActivity::class.java).apply {
                            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        }
                        startActivity(intent)
                    }
                )""", "                AdminAppRoot()")
s = s.replace("fun AdminAppRoot(onOpenClientApp: () -> Unit) {", "fun AdminAppRoot() {")
start = s.find("                    // Switch to Client App")
if start >= 0:
    end = s.find("                    // Emergency Siren toggle", start)
    if end < 0:
        raise SystemExit("Could not find admin top-bar button end marker")
    s = s[:start] + s[end:]
admin.write_text(s)

s = manifest.read_text()
s = s.replace('''            android:name=".MainActivity"
            android:exported="true"''', '''            android:name=".MainActivity"
            android:enabled="${clientActivityEnabled}"
            android:exported="true"''')
s = s.replace('''            android:name=".admin.AdminMainActivity"
            android:exported="true"''', '''            android:name=".admin.AdminMainActivity"
            android:enabled="${adminActivityEnabled}"
            android:exported="true"''')
manifest.write_text(s)

s = gradle.read_text()
if 'flavorDimensions += "appRole"' not in s:
    match = re.search(r'  defaultConfig \{.*?^  \}', s, re.S | re.M)
    if not match:
        raise SystemExit("Could not find app defaultConfig block")
    default_block = re.sub(r'minSdk\s*=\s*\d+', 'minSdk = 29', match.group(0))
    flavors = '''
  
  flavorDimensions += "appRole"
  productFlavors {
    create("client") {
      dimension = "appRole"
      applicationIdSuffix = ".client"
      manifestPlaceholders["clientActivityEnabled"] = "true"
      manifestPlaceholders["adminActivityEnabled"] = "false"
    }
    create("admin") {
      dimension = "appRole"
      applicationIdSuffix = ".admin"
      manifestPlaceholders["clientActivityEnabled"] = "false"
      manifestPlaceholders["adminActivityEnabled"] = "true"
    }
  }
'''
    s = s[:match.start()] + default_block + flavors + s[match.end():]
else:
    # Preserve a minimum supported version of Android 10 even on older ZIP revisions.
    s = re.sub(r'minSdk\s*=\s*\d+', 'minSdk = 29', s, count=1)
gradle.write_text(s)

# Never present hard-coded sample phones as connected remote clients.
security = app / "src/main/java/com/example/manager/SecurityRepository.kt"
if security.exists():
    source = security.read_text()
    start = source.find("        if (_managedDevices.value.isEmpty()) {")
    if start >= 0:
        open_brace = source.find("{", start)
        depth = 0
        end = -1
        for i in range(open_brace, len(source)):
            if source[i] == "{":
                depth += 1
            elif source[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end < 0:
            raise SystemExit("Could not safely locate mock managed-device seed block")
        source = source[:start] + """        // Remote devices must come from a real, consent-based pairing/backend.
        _managedDevices.value = emptyList()""" + source[end:]
        security.write_text(source)

screen = app / "src/main/java/com/example/ui/screens/AdminControllerScreen.kt"
if screen.exists():
    source = screen.read_text()
    source = source.replace(
        'var selectedDeviceId by remember { mutableStateOf("agent_primary") }',
        'var selectedDeviceId by remember { mutableStateOf("") }'
    )
    old_list = """            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                devices.forEach { dev ->
                    DeviceSelectorCard(
                        device = dev,
                        isSelected = dev.deviceId == selectedDeviceId,
                        onSelect = { selectedDeviceId = dev.deviceId }
                    )
                }
            }"""
    new_list = """            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (devices.isEmpty()) {
                    Text(
                        text = "No client connected. This build does not yet have a live pairing backend; remote devices will appear only after an explicit pairing flow is implemented.",
                        color = CyberWarningAmber,
                        fontSize = 13.sp
                    )
                } else {
                    devices.forEach { dev ->
                        DeviceSelectorCard(
                            device = dev,
                            isSelected = dev.deviceId == selectedDeviceId,
                            onSelect = { selectedDeviceId = dev.deviceId }
                        )
                    }
                }
            }"""
    if old_list in source:
        source = source.replace(old_list, new_list, 1)
    screen.write_text(source)

for path in (main, admin):
    content = path.read_text()
    for marker in ("open_admin_app_btn", "open_client_app_btn", "Switch to Admin App Button", "Switch to Client App"):
        if marker in content:
            raise SystemExit(f"Cross-app switch control still present: {marker} in {path}")
print(f"Customized split Client/Admin flavors in {root}")
